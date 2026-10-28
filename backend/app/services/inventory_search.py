"""Search exact identifiers and material descriptions in the current inventory snapshot."""
import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.library import InventoryItem, InventoryState

STOPWORDS = {"donde", "esta", "estan", "hay", "tienen", "tiene", "el", "la", "los", "las",
             "un", "una", "de", "del", "en", "para", "por", "con", "que", "cual", "cuanto",
             "material", "materiales", "inventario", "almacen", "ubicacion", "numero",
             "codigo", "codigos", "sap", "poz", "parte", "partes", "cantidad", "existencia"}


def fold(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower())
                   if not unicodedata.combining(c))


def tokens(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", fold(value))
            if len(word) >= 3 and word not in STOPWORDS}


def search_inventory(db: Session, question: str, limit: int = 8) -> list[dict]:
    wanted = tokens(question)
    if not wanted:
        return []
    state = db.get(InventoryState, 1)
    if not state or not state.sha256:
        return []
    found = []
    for item in db.query(InventoryItem).yield_per(200):
        identifiers = [item.part_number, item.sap_pz, item.sap_pdvsa]
        exact = any(fold(code) in wanted for code in identifiers if code)
        description = tokens(" ".join((item.description, item.equipment, item.manufacturer)))
        overlap = len(wanted & description)
        if not exact and not overlap:
            continue
        score = 1.4 if exact else min(0.55 + 0.12 * (overlap - 1), 0.91)
        if not exact and len(wanted) > 1 and overlap == 1:
            score = 0.38
        fields = [("Descripción", item.description), ("Número de parte", item.part_number),
                  ("Número POZ (SAP Pz)", item.sap_pz), ("SAP PDVSA", item.sap_pdvsa),
                  ("Cantidad", item.quantity), ("Ubicación", item.location),
                  ("Estante", item.shelf), ("Equipo", item.equipment),
                  ("Fabricante", item.manufacturer)]
        content = "; ".join(f"{key}: {value}" for key, value in fields if value)
        found.append({"type": "inventory", "sheet": item.sheet, "row": item.row_number,
                      "title": "Inventario de materiales", "content": content,
                      "score": round(score, 3), "snapshot": state.sha256})
    found.sort(key=lambda item: (-item["score"], item["row"]))
    return found[:limit]
