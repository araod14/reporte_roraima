"""Run with: python -m app.scripts.ingest_library"""
from app.db.session import SessionLocal
from app.services.library_index import ingest_all
from app.services.inventory_index import ingest_inventory

with SessionLocal() as db:
    for path, result in ingest_all(db):
        print(f"{path}: {result}", flush=True)
    print(f"Inventario de materiales.xls: {ingest_inventory(db)}", flush=True)
