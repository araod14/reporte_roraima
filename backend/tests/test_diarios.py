"""Pruebas aisladas: nunca usan la base ni los reportes de producción."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.diario import Diario, VersionDiario
from app.routers.diarios import router
from app.services.diario_service import gus_catalogo


class DiariosTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        app = FastAPI()
        app.include_router(router)

        def database():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(username="inspector")
        self.client = TestClient(app)
        self.settings = patch("app.services.diario_service.settings", SimpleNamespace(REPORTS_DIR=self.temp.name))
        self.settings.start()
        self.payload = {
            "id": str(uuid4()), "version": 0,
            "client_updated_at": datetime.now(timezone.utc).isoformat(),
            "datos": {"fecha": "2026-09-12", "hora": "09:30", "responsable": "José Pérez",
                      "lcn_a": "OK", "lcn_b": "SUSPECT",
                      "gus": {c["codigo"]: ["OK", "MALO", "OBSERVACION"][i % 3] for i, c in enumerate(gus_catalogo())},
                      "temperatura_ish1": 24.5, "temperatura_ish2": -1.2, "observaciones": "Revisión de señal. °C"},
        }
        self.url = f"/api/diarios/{self.payload['id']}"

    def tearDown(self):
        self.client.close()
        self.settings.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def save(self):
        return self.client.put(self.url, json=self.payload)

    def close(self, version=0, timestamp=None):
        return self.client.post(self.url + "/finalizar", json={
            "version": version, "client_updated_at": timestamp or self.payload["client_updated_at"],
        })

    def test_draft_can_be_incomplete_but_cannot_finalize(self):
        self.payload["datos"] = {"fecha": "2026-09-12", "hora": "10:00"}
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.close().status_code, 422)
        self.assertEqual(self.client.get(self.url).json()["estado"], "BORRADOR")

    def test_invalid_states_temperatures_and_catalog(self):
        for field, bad in (("lcn_a", "MALO"), ("temperatura_ish1", "infinity"),
                           ("hora", "25:30"), ("observaciones", "a" * 1001), ("gus", {"unknown": "OK"})):
            with self.subTest(field=field):
                original = self.payload["datos"][field]
                self.payload["datos"][field] = bad
                self.assertEqual(self.save().status_code, 422)
                self.payload["datos"][field] = original

    def test_all_gus_and_nonblank_responsible_required(self):
        self.payload["datos"]["gus"].pop(next(iter(self.payload["datos"]["gus"])))
        self.save()
        self.assertEqual(self.close().status_code, 422)
        self.payload["datos"]["gus"] = {c["codigo"]: "OK" for c in gus_catalogo()}
        self.payload["datos"]["responsable"] = "   "
        self.payload["client_updated_at"] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        self.save()
        self.assertEqual(self.close().status_code, 422)

    def test_sync_retries_and_older_edits(self):
        first = self.client.post("/api/diarios/sync", json={"diarios": [self.payload]}).json()
        self.assertEqual(first["results"][0]["status"], "created")
        self.assertEqual(self.save().json()["status"], "skipped_older")
        self.payload["client_updated_at"] = "2000-01-01T00:00:00+00:00"
        self.payload["datos"]["responsable"] = "Viejo"
        self.assertEqual(self.save().json()["status"], "skipped_older")
        self.assertEqual(len(self.client.get("/api/diarios").json()), 1)
        self.assertEqual(self.client.get(self.url).json()["datos"]["responsable"], "José Pérez")

    def test_png_hash_download_and_close_retry(self):
        self.save()
        response = self.close()
        self.assertEqual(response.status_code, 200, response.text)
        meta = response.json()["versiones"][0]
        image = self.client.get(meta["png_url"])
        self.assertEqual(image.headers["content-type"], "image/png")
        self.assertEqual(hashlib.sha256(image.content).hexdigest(), meta["png_sha256"])
        with Image.open(io.BytesIO(image.content)) as png:
            self.assertEqual(png.width, 1080)
            self.assertGreater(png.height, png.width)
        canonical = json.dumps(response.json()["datos"], sort_keys=True, ensure_ascii=False).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), meta["content_hash"])
        self.assertEqual(self.close().json()["version"], 1)
        self.assertEqual(self.client.get(meta["png_url"]).content, image.content)
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.png"))), 1)

    def test_reopen_preserves_old_image_and_rejects_stale_draft(self):
        self.save()
        original = self.close().json()["versiones"][0]
        png = self.client.get(original["png_url"]).content
        reopened = self.client.post(self.url + "/reabrir", json={"version": 1}).json()
        self.assertEqual(reopened["estado"], "BORRADOR")
        self.assertEqual(self.save().json()["status"], "skipped_version")
        self.payload["version"] = 1
        self.payload["client_updated_at"] = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
        self.payload["datos"]["observaciones"] = "Corrección"
        self.save()
        result = self.close(version=1).json()
        self.assertEqual(result["version"], 2)
        self.assertEqual(len(result["versiones"]), 2)
        self.assertEqual(self.client.get(original["png_url"]).content, png)
        with Session(self.engine) as session:
            versions = session.scalars(select(VersionDiario).order_by(VersionDiario.version)).all()
            self.assertNotEqual(versions[0].datos["observaciones"], versions[1].datos["observaciones"])

    def test_concurrent_edit_detected_before_close(self):
        self.save()
        timestamp = self.payload["client_updated_at"]
        self.payload["client_updated_at"] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        self.payload["datos"]["lcn_a"] = "SUSPECT"
        self.save()
        self.assertEqual(self.close(timestamp=timestamp).status_code, 409)
        self.assertEqual(self.client.get(self.url).json()["estado"], "BORRADOR")

    def test_render_failure_keeps_draft(self):
        self.save()
        with patch("app.services.diario_service.generar_png", side_effect=RuntimeError("render failed")):
            with self.assertRaises(RuntimeError):
                self.close()
        self.assertEqual(self.client.get(self.url).json()["estado"], "BORRADOR")
        self.assertEqual(self.client.get(self.url + "/versiones").json(), [])

    def test_multiple_reports_same_date(self):
        self.save()
        other = dict(self.payload, id=str(uuid4()))
        self.assertEqual(self.client.put(f"/api/diarios/{other['id']}", json=other).status_code, 200)
        self.assertEqual(len(self.client.get("/api/diarios").json()), 2)

    def test_long_observations_expand_without_changing_width(self):
        self.save()
        first = self.close().json()["versiones"][0]
        first_image = Image.open(io.BytesIO(self.client.get(first["png_url"]).content))
        self.client.post(self.url + "/reabrir", json={"version": 1})
        self.payload["version"] = 1
        self.payload["client_updated_at"] = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
        self.payload["datos"]["observaciones"] = "Á" * 1000
        self.save()
        second = self.close(version=1).json()["versiones"][-1]
        second_image = Image.open(io.BytesIO(self.client.get(second["png_url"]).content))
        self.assertGreater(second_image.height, first_image.height)
        self.assertEqual(second_image.width, 1080)

    def test_id_mismatch_and_missing_version(self):
        self.assertEqual(self.client.put(f"/api/diarios/{uuid4()}", json=self.payload).status_code, 400)
        self.save()
        self.assertEqual(self.client.get(self.url + "/versiones/99/imagen").status_code, 404)


if __name__ == "__main__":
    unittest.main()
