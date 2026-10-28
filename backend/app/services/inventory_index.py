"""Atomic import of the material inventory spreadsheet."""
import hashlib
import re
import unicodedata
from pathlib import Path

import xlrd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.library import InventoryItem, InventoryState, now

FILENAME = "Inventario de materiales.xls"
HEADERS = ("Descripción", "Número de Partes", "SAP Pz", "Fabricante", "Cantidad",
           "Equipo", "Ubicación", "Estantes", "Sap PDVSA")


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return re.sub(r"\s+", " ", "".join(c for c in value if not unicodedata.combining(c)).lower()).strip()


def cell(sheet, row: int, column: int) -> str:
    value = sheet.cell_value(row, column)
    if value is None or value == "":
        return ""
    if sheet.cell_type(row, column) == xlrd.XL_CELL_NUMBER:
        return str(int(value)) if value == int(value) else format(value, "g")
    return str(value).strip()


def parse_inventory(contents: bytes) -> list[dict]:
    workbook = xlrd.open_workbook(file_contents=contents, on_demand=True)
    try:
        sheet = workbook.sheet_by_name("Hoja1")
        header_row = next((row for row in range(min(sheet.nrows, 30))
                           if normalized(cell(sheet, row, 1)) == "descripcion"), None)
        if header_row is None:
            raise ValueError("No se encontró la cabecera de la hoja Hoja1")
        columns = {normalized(cell(sheet, header_row, col)): col for col in range(sheet.ncols)
                   if cell(sheet, header_row, col)}
        missing = [name for name in HEADERS if normalized(name) not in columns]
        if missing:
            raise ValueError(f"Faltan columnas: {', '.join(missing)}")
        def value(row: int, name: str) -> str:
            return cell(sheet, row, columns[normalized(name)])
        items = []
        for row in range(header_row + 1, sheet.nrows):
            description = value(row, "Descripción")
            if not description:
                continue
            items.append(dict(sheet=sheet.name, row_number=row + 1, description=description,
                part_number=value(row, "Número de Partes"), sap_pz=value(row, "SAP Pz"),
                sap_pdvsa=value(row, "Sap PDVSA"), manufacturer=value(row, "Fabricante"),
                quantity=value(row, "Cantidad"), equipment=value(row, "Equipo"),
                location=value(row, "Ubicación"), shelf=value(row, "Estantes")))
        if not items:
            raise ValueError("La hoja de inventario no contiene materiales")
        return items
    finally:
        workbook.release_resources()


def ingest_inventory(db: Session) -> str:
    state = db.get(InventoryState, 1)
    try:
        contents = (Path(settings.LIBRARY_PDF_DIR) / FILENAME).read_bytes()
        digest = hashlib.sha256(contents).hexdigest()
        if state and state.sha256 == digest and not state.last_error:
            return "unchanged"
        items = parse_inventory(contents)
        db.query(InventoryItem).delete()
        db.add_all(InventoryItem(**item) for item in items)
        if state is None:
            state = InventoryState(id=1)
            db.add(state)
        state.sha256, state.row_count, state.last_error, state.updated_at = digest, len(items), "", now()
        db.commit()
        return f"indexed {len(items)} materials"
    except Exception as exc:
        db.rollback()
        state = db.get(InventoryState, 1)
        if state is None:
            state = InventoryState(id=1, sha256="", row_count=0)
            db.add(state)
        state.last_error = str(exc)[:500]
        db.commit()
        return f"ERROR: {state.last_error}"
