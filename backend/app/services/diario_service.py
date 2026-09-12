"""Persistencia offline y PNG: una imagen guardada por versión."""
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.catalogo_data import catalogo_rows
from app.core.config import settings
from app.models.diario import Diario, VersionDiario
from app.schemas.diario import DiarioIn, DatosDiario


def gus_catalogo():
    return [c for c in catalogo_rows() if c["nombre"].startswith("GUS")]


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def lock_diario(db: Session, diario_id: str):
    # También serializa la creación inicial, cuando aún no existe una fila.
    if db.bind.dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(diario_id.encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    return db.scalar(select(Diario).where(Diario.id == diario_id).with_for_update())


def validar_gus(datos: DatosDiario):
    if set(datos.gus) - {c["codigo"] for c in gus_catalogo()}:
        raise HTTPException(422, "El reporte contiene GUS fuera del catálogo")


def validar_cierre(datos: DatosDiario):
    validar_gus(datos)
    if (not datos.responsable.strip() or not datos.lcn_a or not datos.lcn_b
            or not datos.ucn1 or not datos.ucn2 or not datos.ucn3
            or datos.temperatura_ish1 is None or datos.temperatura_ish2 is None
            or set(datos.gus) != {c["codigo"] for c in gus_catalogo()}):
        raise HTTPException(422, "Complete responsable, LCN, UCN1, UCN2, UCN3, todas las GUS y ambas temperaturas")


def upsert_diario(db: Session, data: DiarioIn, username: str):
    validar_gus(data.datos)
    item = lock_diario(db, str(data.id))
    status = "created"
    if item:
        if item.estado == "FINALIZADA":
            return item, "skipped_finalizada"
        if item.version != data.version:
            return item, "skipped_version"
        if utc(item.client_updated_at) >= utc(data.client_updated_at):
            return item, "skipped_older"
        status = "updated"
    else:
        if data.version != 0:
            raise HTTPException(409, "La versión del diario no existe")
        item = Diario(id=str(data.id), created_by=username, version=0, estado="BORRADOR")
        db.add(item)
    item.datos = data.datos.model_dump(mode="json")
    item.client_updated_at = data.client_updated_at
    item.updated_at = datetime.now(timezone.utc)
    db.flush()
    return item, status


def generar_png(datos: dict, version: int) -> bytes:
    """Dibuja texto medido y envuelto; el alto crece con las observaciones."""
    candidates = [
        ("/usr/share/fonts/truetype/dejavu", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu-sans-fonts", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2", "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
        ("/usr/share/fonts/liberation-sans-fonts", "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
    ]
    fonts = next(((Path(folder) / normal, Path(folder) / heavy)
                  for folder, normal, heavy in candidates
                  if (Path(folder) / normal).exists() and (Path(folder) / heavy).exists()), None)
    if fonts is None:
        raise HTTPException(500, "Instale las fuentes DejaVu Sans o Liberation Sans en el servidor")
    regular = ImageFont.truetype(str(fonts[0]), 42)
    bold = ImageFont.truetype(str(fonts[1]), 44)
    title = ImageFont.truetype(str(fonts[1]), 58)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    rows = []

    def line(value, font=regular, color="#172b43", background=None):
        # Envuelve también palabras largas y respeta saltos de línea.
        for paragraph in str(value).split("\n"):
            current = ""
            for char in paragraph:
                if measure.textlength(current + char, font=font) > 936:
                    split = current.rfind(" ")
                    if split > 0:
                        rows.append((current[:split], font, color, background))
                        current = current[split + 1:] + char
                    else:
                        rows.append((current, font, color, background))
                        current = char
                else:
                    current += char
            rows.append((current, font, color, background))

    def section(label):
        line("", regular)
        line(label, bold, "#0b5cad")

    line("REPORTE DIARIO", title, "#0b5cad")
    line("ISH / SDC — Roraima", bold)
    line(f'{datos["fecha"]}  ·  {datos["hora"]} (Venezuela)')
    line(f'Responsable: {datos["responsable"]}')
    section("ESTADO LCN")
    colors = {"OK": ("#176334", "#e7f6ec"), "SUSPECT": ("#704800", "#fff2cd"),
              "FAIL": ("#a61d24", "#fdeceb"), "MALO": ("#a61d24", "#fdeceb"), "OBSERVACION": ("#704800", "#fff2cd")}

    def status_line(label, state):
        color, background = colors[state]
        line(f'{label}   ·   {"OBSERVACIÓN" if state == "OBSERVACION" else "Fail" if state == "FAIL" else state}', regular, color, background)

    status_line("LCN A", datos["lcn_a"])
    status_line("LCN B", datos["lcn_b"])
    section("ESTADO UCN")
    for key in ("ucn1", "ucn2", "ucn3"):
        status_line(key.upper(), datos[key])
    section("TEMPERATURAS")
    for key, label in (("temperatura_ish1", "ISH-1"), ("temperatura_ish2", "ISH-2")):
        line(f'{label}   ·   {datos[key]:g} °C')
    section("ESTADO GUS")
    for cat in gus_catalogo():
        status_line(cat["nombre"], datos["gus"][cat["codigo"]])
    section("OBSERVACIONES")
    line(datos["observaciones"].strip() or "Sin observaciones")
    line("")
    line(f"Versión {version}", regular, "#526176")
    heights = [84 if font is title else 66 for _, font, _, _ in rows]
    im = Image.new("RGB", (1080, 96 + sum(heights)), "white")
    draw = ImageDraw.Draw(im)
    y = 48
    for (value, font, color, background), height in zip(rows, heights):
        if background:
            draw.rounded_rectangle((48, y, 1032, y + height - 4), radius=8, fill=background)
        draw.text((72, y + 6), value, font=font, fill=color)
        y += height
    stream = io.BytesIO()
    im.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def finalizar_diario(db: Session, item: Diario, username: str):
    datos = DatosDiario.model_validate(item.datos)
    validar_cierre(datos)
    version = item.version + 1
    snapshot = datos.model_dump(mode="json")
    png = generar_png(snapshot, version)
    digest = hashlib.sha256(png).hexdigest()
    # Nombre por contenido: jamás se sobreescribe una imagen diferente, incluso
    # si un proceso cae después de escribir el archivo y antes del commit.
    directory = Path(settings.REPORTS_DIR) / "diarios" / item.id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"v{version}-{digest}.png"
    try:
        with path.open("xb") as file:
            file.write(png)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise HTTPException(500, "Archivo de reporte incompleto; requiere revisión")
    rep = VersionDiario(
        diario_id=item.id, version=version, datos=snapshot, png_path=str(path),
        png_sha256=digest,
        content_hash=hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        generado_por=username,
    )
    db.add(rep)
    item.version = version
    item.estado = "FINALIZADA"
    item.updated_at = datetime.now(timezone.utc)
    db.flush()
    return rep
