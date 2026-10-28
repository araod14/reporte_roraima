import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.library import InventoryItem, InventoryState
from app.services.inventory_index import FILENAME, ingest_inventory, parse_inventory
from app.services.inventory_search import search_inventory


SOURCE = Path(__file__).resolve().parents[2] / "info_tps" / FILENAME
if not SOURCE.is_file():
    SOURCE = Path(settings.LIBRARY_PDF_DIR) / FILENAME


@unittest.skipUnless(SOURCE.is_file(), "El XLS privado no está presente")
class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        shutil.copyfile(SOURCE, Path(self.directory.name) / FILENAME)
        self.patch = patch.object(settings, "LIBRARY_PDF_DIR", self.directory.name)
        self.patch.start()
        self.engine = create_engine("sqlite:///:memory:")
        InventoryState.__table__.create(self.engine)
        InventoryItem.__table__.create(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.patch.stop()
        self.directory.cleanup()

    def test_import_exact_codes_and_zero_quantity(self):
        expected = parse_inventory(SOURCE.read_bytes())
        with Session(self.engine) as db:
            self.assertEqual(ingest_inventory(db), f"indexed {len(expected)} materials")
            self.assertEqual(ingest_inventory(db), "unchanged")
            first = expected[0]
            self.assertEqual(db.query(InventoryItem).count(), len(expected))
            for field in ("part_number", "sap_pz", "sap_pdvsa"):
                if first[field]:
                    hits = search_inventory(db, f"¿Dónde está el material {first[field]}?")
                    self.assertEqual(hits[0]["row"], first["row_number"])
            zero = next(item for item in expected if item["quantity"] == "0")
            hit = search_inventory(db, f"SAP {zero['sap_pz']}")[0]
            self.assertIn("Cantidad: 0", hit["content"])

    def test_invalid_replacement_keeps_last_valid_snapshot(self):
        with Session(self.engine) as db:
            ingest_inventory(db)
            count = db.query(InventoryItem).count()
            (Path(self.directory.name) / FILENAME).write_bytes(b"invalid XLS")
            self.assertTrue(ingest_inventory(db).startswith("ERROR:"))
            self.assertEqual(db.query(InventoryItem).count(), count)
            self.assertTrue(db.get(InventoryState, 1).last_error)


if __name__ == "__main__":
    unittest.main()
