"""Incremental, local-only PDF extraction and multilingual embeddings."""
import hashlib
import os
import re
from pathlib import Path

import fitz
import numpy as np
from fastembed import TextEmbedding
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.library import LibraryChunk, LibraryDocument, now

_model = None


def model():
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=settings.LIBRARY_EMBEDDING_MODEL,
                               cache_dir=os.getenv("HF_HOME"))
    return _model


def embed(texts: list[str], *, query: bool = False) -> list[bytes]:
    vectors = model().embed(texts, batch_size=16)
    normalized = []
    for vector in vectors:
        value = np.asarray(vector, dtype="<f4")
        value /= max(float(np.linalg.norm(value)), 1e-12)
        normalized.append(value.tobytes())
    return normalized


def language(text: str) -> str:
    sample = " " + text.lower() + " "
    return "es" if sum(sample.count(w) for w in (" de ", " para ", " el ", " la ", " configuración ")) > sum(sample.count(w) for w in (" the ", " and ", " for ", " with ")) else "en"


def chunks_for_page(text: str):
    # Preserve paragraph/table rows and keep procedures together within one page.
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    section = ""
    buffer: list[str] = []
    for line in lines:
        if len(line) < 110 and (re.match(r"^(\d+(?:\.\d+)*\s+|[A-Z][A-Z\s]{6,}$)", line)):
            section = line[:160]
        if sum(map(len, buffer)) + len(line) > 1200 and buffer:
            yield section, "\n".join(buffer)
            buffer = buffer[-3:] if len(buffer) > 3 else []
        buffer.append(line)
    if sum(map(len, buffer)) >= 80:
        yield section, "\n".join(buffer)


def ingest_file(db: Session, file: Path, root: Path) -> str:
    relative = str(file.relative_to(root))
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    existing = db.query(LibraryDocument).filter_by(path=relative).first()
    if existing and existing.sha256 == digest:
        return "unchanged"
    pdf = fitz.open(file)
    pages = []
    needs_ocr = []
    seen = set()
    for number, page in enumerate(pdf, 1):
        text = page.get_text("text", sort=True)
        if len(text.strip()) < 80:
            needs_ocr.append(number)
            try:
                text = page.get_text("text", textpage=page.get_textpage_ocr(language="eng+spa", dpi=160), sort=True)
            except Exception:
                pass
        for section, content in chunks_for_page(text):
            chash = hashlib.sha256(re.sub(r"\s+", " ", content).encode()).hexdigest()
            if chash in seen:
                continue
            seen.add(chash)
            pages.append((number, section, content, chash))
    title = (pdf.metadata.get("title") or "").strip()
    title = f"{title} ({file.stem})" if title and title.lower() not in ("untitled", file.stem.lower()) else file.stem
    title = title[:300]
    count = len(pdf)
    pdf.close()
    if existing is None:
        existing = LibraryDocument(path=relative, title=title, sha256=digest, pages=count)
        db.add(existing)
        db.flush()
    else:
        db.query(LibraryChunk).filter_by(document_id=existing.id).delete()
        existing.title, existing.sha256, existing.pages = title, digest, count
    existing.ocr_pages = ",".join(map(str, needs_ocr))
    existing.updated_at = now()
    for start in range(0, len(pages), 32):
        batch = pages[start:start + 32]
        vectors = embed([item[2] for item in batch])
        for (page, section, content, chash), vector in zip(batch, vectors):
            db.add(LibraryChunk(document_id=existing.id, page=page, section=section,
                                content=content, content_hash=chash, language=language(content), embedding=vector))
    db.commit()
    return f"indexed {len(pages)} chunks; OCR needed on {len(needs_ocr)} pages"


def ingest_all(db: Session):
    root = Path(settings.LIBRARY_PDF_DIR).resolve()
    if not root.is_dir():
        raise RuntimeError(f"PDF directory missing: {root}")
    files = sorted(root.rglob("*.pdf"))
    for file in files:
        try:
            yield str(file.relative_to(root)), ingest_file(db, file, root)
        except Exception as exc:
            db.rollback()
            yield str(file.relative_to(root)), f"ERROR: {exc}"
