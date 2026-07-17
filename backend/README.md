# Backend — API de Verificación ISH y SDC

FastAPI + PostgreSQL + SQLAlchemy + Alembic + WeasyPrint.

## Endpoints principales

- `POST /api/auth/login` — login (usuarios precreados). Devuelve JWT.
- `GET  /api/auth/me` — usuario actual.
- `GET  /api/catalogo` — catálogo fijo de elementos (95).
- `GET  /api/inspecciones` — lista.
- `GET  /api/inspecciones/{id}` — detalle con registros.
- `PUT  /api/inspecciones/{id}` — crear/actualizar (upsert por UUID).
- `POST /api/inspecciones/{id}/finalizar` — congela y genera el reporte vN (PDF+HTML+hashes).
- `POST /api/inspecciones/{id}/reabrir` — reabre para corregir (la próxima finalización crea vN+1).
- `POST /api/sync/batch` — sincronización por lotes idempotente.
- `GET  /api/reportes/{inspeccion_id}` — versiones de reporte.
- `GET  /verificar/{inspeccion_id}/{version}` — **página pública** de verificación (QR).
- `GET  /api/docs` — Swagger.

## Modelo de datos

- **User** — usuarios fijos.
- **CatalogoElemento** — catálogo fijo (`tipo` ∈ SIMPLE | CCC | UPS); `codigo =
  "{instalacion}|{sistema}|{nombre}"`. `02PLC01` tiene `ups_dobles=true` (4 fuentes).
- **Inspeccion** — cabecera; `id` = UUID de cliente; `estado` ∈ BORRADOR | FINALIZADA.
- **Registro** — valores por elemento (columnas nullable según el tipo).
- **Reporte** — una fila por versión finalizada, con `pdf_sha256`, `html_sha256`,
  `content_hash`, rutas de archivos. Nunca se sobreescribe.

## Correr en local (sin Docker)

Requiere las libs de sistema de WeasyPrint (Pango/Cairo/gdk-pixbuf) instaladas y un
PostgreSQL accesible.

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql+psycopg://roraima:roraima@localhost:5432/roraima"
export BASE_URL="http://localhost:8000"
export REPORTS_DIR="./_reports"
export JWT_SECRET="dev-secret"

python -m app.seed                       # crea tablas (create_all) + catálogo + usuarios
uvicorn app.main:app --reload --port 8000
```

## Migraciones (Alembic)

El seed usa `create_all` para el arranque inicial. Para cambios de esquema posteriores:

```bash
alembic revision --autogenerate -m "descripcion del cambio"
alembic upgrade head
```

`alembic/env.py` toma la URL de `DATABASE_URL` e importa `app.models` para el autogenerate.

## Reportes y hash

Ver `app/services/report_service.py`. Los archivos se escriben en
`REPORTS_DIR/{inspeccion_id}/v{n}.{html,pdf}` una sola vez. El hash de bytes se calcula
sobre exactamente esos archivos; por eso **no deben regenerarse**.
