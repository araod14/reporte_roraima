"""Hybrid search over local PostgreSQL chunks; no document leaves this service."""
import heapq
import re
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.library import LibraryChunk, LibraryDocument
from app.services.library_index import embed

CODE = re.compile(r"\b(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{3,}\b", re.I)


def search(db: Session, question: str, limit_chars: int = 26000) -> list[dict]:
    query = np.frombuffer(embed([question], query=True)[0], dtype="<f4")
    best: list[tuple[float, str]] = []
    # Embeddings are compact float32 BLOBs. Stream rows so memory stays bounded.
    rows = db.query(LibraryChunk.id, LibraryChunk.embedding).yield_per(512)
    for ident, raw in rows:
        vector = np.frombuffer(raw, dtype="<f4")
        if vector.size != query.size:
            continue
        score = float(np.dot(query, vector))
        if len(best) < 30:
            heapq.heappush(best, (score, ident))
        elif score > best[0][0]:
            heapq.heapreplace(best, (score, ident))
    scores = {ident: score for score, ident in best}
    exact = list(dict.fromkeys(CODE.findall(question)))[:8]
    for code in exact:
        for (ident,) in db.query(LibraryChunk.id).filter(LibraryChunk.content.ilike(f"%{code}%")).limit(30):
            scores[ident] = max(scores.get(ident, 0), 1.2)
        matching = db.query(LibraryDocument.id).filter(LibraryDocument.path.ilike(f"%{code}%")).limit(10)
        for (document_id,) in matching:
            for (ident,) in db.query(LibraryChunk.id).filter_by(document_id=document_id).limit(3):
                scores[ident] = max(scores.get(ident, 0), 1.1)
    if db.bind.dialect.name == "postgresql":
        found = db.execute(text("""SELECT id FROM library_chunks
            WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', :q)
            LIMIT 30"""), {"q": question[:300]}).all()
        for (ident,) in found:
            scores[ident] = max(scores.get(ident, 0), 0.95)
    if not scores:
        return []
    chunks = {c.id: c for c in db.query(LibraryChunk).filter(LibraryChunk.id.in_(scores))}
    documents = {d.id: d for d in db.query(LibraryDocument).filter(
        LibraryDocument.id.in_({c.document_id for c in chunks.values()}))}
    result, used = [], 0
    for ident, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        c = chunks.get(ident)
        if not c or used + len(c.content) > limit_chars:
            continue
        d = documents[c.document_id]
        result.append({"id": c.id, "document_id": d.id, "title": d.title,
                       "path": d.path, "page": c.page, "section": c.section,
                       "language": c.language, "content": c.content, "score": round(score, 3)})
        used += len(c.content)
    return result


TOPIC = re.compile(r"(?i)\b(TPS|Honeywell|HPM|GUS|UCN|NIM|LCN|LLMUX|FTA|alarma|controlador|módulo|modulo|punto|display|manual(?:es)?|procedimiento|equipo|código|codigo|failover|redundan\w*|swap|hardware|software|release|R\d+(?:\.\d+)?|inventario|material(?:es)?|almac[eé]n|ubicaci[oó]n|existencia|cantidad|SAP|POZ|parte(?:s)?)\b")
OUTSIDE = re.compile(r"(?i)\b(clima|weather|receta|pastel|fútbol|futbol|política|politica|bolsa|bitcoin|wifi|teléfono|telefono|secreto|contraseña|password|token|clave api)\b")
INJECTION = re.compile(r"(?i)\b(ignora|olvida|desobedece|ignore|forget|disregard|revela|muestra)\b.{0,70}\b(instrucciones|reglas|instructions|rules|secreto|contraseña|password|token|clave)\b")
FOLLOWUP = re.compile(r"(?i)\b(y|eso|ese|esa|esta|este|también|tambien|cómo|como|qué|que|cuál|cual)\b")
GREETING = re.compile(r"(?i)(hola|buenas|hello|hi|ayuda|qué puedes hacer|que puedes hacer)[.!?\s]*")


def scope_question(question: str, history: list[str], results: list[dict]) -> tuple[str, str]:
    q = question.strip()
    if GREETING.fullmatch(q):
        return "help", q
    clauses = re.split(r"(?<=[.!?])\s+|\s+(?:y|además|ademas)\s+", q)
    relevant = []
    inventory_match = any(item.get("type") == "inventory" and item.get("score", 0) >= 0.55
                          for item in results)
    for clause in clauses:
        if INJECTION.search(clause) or OUTSIDE.search(clause):
            continue
        if TOPIC.search(clause) or CODE.search(clause) or re.search(r"\b\d{5,}\b", clause) or inventory_match or ((relevant or history) and FOLLOWUP.search(clause)):
            relevant.append(clause.strip())
    if not relevant:
        return "outside", q
    scoped = " y ".join(relevant)
    if not results or results[0]["score"] < 0.42:
        return "insufficient", scoped
    return "answer", scoped
