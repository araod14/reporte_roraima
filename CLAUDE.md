# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

App to digitize the PDVSA "Verificación Periódica de ISH y SDC" industrial inspection
form. Offline-first field app (~6 engineers, poor connectivity) that syncs to a central
backend. On finalize, the backend produces a PDF + HTML report with a SHA-256 integrity
hash and a QR code linking to a public verification page.

Three parts: **`backend/`** (FastAPI API + report generation), **`app/`** (installable
PWA, the field app), **`deploy/`** (docker-compose + Caddy for the VPS).

Detailed human docs live in `README.md` (overview), `deploy/README.md` (VPS deploy +
backups), `backend/README.md`, and `app/README.md`. Default git branch is `main`.

## Commands

### Backend (local, no Docker — fastest here)
The host has Pango/Cairo/gdk-pixbuf so WeasyPrint runs natively. Use **python3.12** (the
repo-root `venv/` is Python 3.14 with poor wheel support — do not use it).

```bash
docker run -d --name roraima_pg -e POSTGRES_USER=roraima -e POSTGRES_PASSWORD=roraima \
  -e POSTGRES_DB=roraima -p 5433:5432 postgres:16
cd backend && python3.12 -m venv .venv312 && .venv312/bin/pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://roraima:roraima@localhost:5433/roraima" \
       BASE_URL="http://localhost:8010" REPORTS_DIR="./_reports" JWT_SECRET="dev-secret"
.venv312/bin/python -m app.seed                        # create_all + catalog + users
.venv312/bin/uvicorn app.main:app --port 8010          # Swagger at /api/docs
```
Port 8000 is usually taken by another container here — use **8010**.

### Backend (Docker, matches production)
```bash
cd deploy && docker compose -f docker-compose.dev.yml up --build   # db + api on :8010
```
Note: the Docker build's apt layer is slow/flaky in this sandbox's network; it builds
fine on a normal network. Base is pinned to `python:3.12-slim-bookworm`.

### User management
```bash
.venv312/bin/python -m scripts.manage_users list|add|passwd|rename|delete ...
# In Docker: docker compose exec api python -m scripts.manage_users list
```

### PWA
```bash
cd app && npm ci
npm run dev        # Vite dev server (proxies /api -> localhost:8010); lands on 5175 if 5174 busy
npm run build      # tsc -b && vite build -> app/dist  (Caddy serves this in deploy/)
```
There are no automated tests; verification is done by driving the running API (curl) and
the PWA (browser). Backend smoke test against a running API on `:8010`:

```bash
API=http://localhost:8010
TOKEN=$(curl -s -X POST $API/api/auth/login \
  -d "username=darao&password=roraima2026" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s $API/api/catalogo -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;print(len(json.load(sys.stdin)),'elementos')"  # -> 95
# create/sync an inspection (idempotent by UUID), then:
curl -s -X POST $API/api/inspecciones/<UUID>/finalizar -H "Authorization: Bearer $TOKEN"  # -> pdf_sha256 == sha256sum of the served /reports/<UUID>/v1.pdf
```
Seed users: `darao`, `ldavila`, `smartinez`, `mlanz`, `frojas`, `admin` (password = `SEED_PASSWORD`, default `roraima2026`).

### Full VPS deploy
`cd deploy && cp .env.example .env` (set DOMAIN/BASE_URL/JWT_SECRET/passwords) → build the
PWA (`cd ../app && npm run build`) → `cd ../deploy && docker compose up -d --build`. The
`api` entrypoint waits for Postgres, runs `alembic upgrade head`, then the idempotent seed.

## Architecture

### Data model & the fixed catalog
- **`CatalogoElemento`** is seeded once (95 rows, exact order/names matter — they mirror the
  paper form). Stable key `codigo = "{instalacion}|{sistema}|{nombre}"`. Three `tipo`s drive
  everything: **SIMPLE** (estado OK/MALO/OBSERVACION + comment), **CCC** (adds valor_a/b),
  **UPS** (fuente/bateria/fan booleans ×2, or ×4 when `ups_dobles` — only `ISH-2|PLC|02PLC01`).
- The catalog lives in **`backend/app/catalogo_data.py`** and is duplicated into the PWA as
  **`app/src/catalogo.ts`** (bundled offline fallback). If you change the catalog, regenerate
  the TS from the Python source rather than hand-editing.
- **`Inspeccion.id`** and **`Registro.id`** are **client-generated UUIDs** — this is what
  makes batch sync idempotent. `estado` ∈ BORRADOR | FINALIZADA.

### Offline-first sync (the core flow)
The PWA is the source of truth while offline. Every edit autosaves to IndexedDB (Dexie,
`app/src/db.ts`) with `syncState: pending`. `app/src/sync.ts` uploads all pending
inspections to `POST /api/sync/batch` on reconnect (`online` event + 60s interval) and via
a manual button. The backend upsert (`backend/app/services/inspeccion_service.py`) keys on
UUID, resolves conflicts with `client_updated_at` (newest wins), and refuses edits to a
FINALIZADA inspection. Re-sending the same batch never duplicates.

### Report generation & integrity (`backend/app/services/report_service.py`)
On `POST /api/inspecciones/{id}/finalizar`: data is frozen, `reporte.html.j2` +
`reporte.css` render to HTML, WeasyPrint renders the **same HTML** to PDF. Both files are
written **once** to `REPORTS_DIR/{id}/v{n}.{html,pdf}` and **never regenerated** (regen
would change PDF bytes and break the byte-hash). A new `Reporte` row stores `pdf_sha256`,
`html_sha256`, and `content_hash`.

Integrity design (important, non-obvious): a file cannot contain its own byte-hash, so the
**visible** hash stamped in the PDF footer is the `content_hash` (SHA-256 of the frozen
data JSON — deterministic, embeddable). The QR encodes the URL
`BASE_URL/verificar/{id}/{version}`. That public page (`backend/app/routers/verificar.py`,
no auth) shows all hashes and lets a recipient drop the received PDF to compare its actual
SHA-256 against the stored `pdf_sha256`. Corrections go through `/reabrir` → next finalize
creates v2; v1 files/hashes stay intact.

### Serving & routing
In production Caddy is the single entrypoint: serves the PWA, proxies `/api/*` and
`/verificar/*` to the API, and serves `/reports/*` from the reports volume. The PWA uses
`HashRouter` and, when same-origin, calls `/api` directly (no config); `VITE_API_BASE_URL`
is only needed if the PWA is served from a different domain than the API.

## Gotchas
- **Don't regenerate report files** for an existing version — it invalidates the stored hash.
- **`bcrypt` is pinned to 4.0.1** (passlib 1.7.4 logs a noisy traceback with bcrypt ≥4.1).
- Alembic is wired for future migrations but the initial schema is created via `create_all`
  in the seed; there are no version files yet.
