# Repository Guidelines

## Project Structure & Module Organization

- `app/` contains the React 18, TypeScript, and Vite offline-first PWA. UI pages live in `app/src/pages/`; API, IndexedDB, synchronization, and report-sharing logic live directly under `app/src/`. Static icons are in `app/public/`.
- `backend/` contains the FastAPI service. Keep HTTP handlers in `backend/app/routers/`, business logic in `services/`, persistence models in `models/`, request/response types in `schemas/`, and report templates/styles in `templates/` and `static/`.
- `deploy/` holds Docker Compose and Caddy configuration. Root and component READMEs document architecture and operations.

## Build, Test, and Development Commands

Run commands from the indicated component directory:

```bash
cd app && npm ci && npm run dev       # PWA dev server; proxies /api to :8010
cd app && npm run build               # Type-check and build app/dist
cd app && npm run preview             # Preview the production build
cd deploy && docker compose -f docker-compose.dev.yml up --build
```

For a native backend setup, use Python 3.12, install `backend/requirements.txt`, configure `DATABASE_URL`, `BASE_URL`, `REPORTS_DIR`, and `JWT_SECRET`, then run `python -m app.seed` and `uvicorn app.main:app --reload --port 8010` from `backend/`.

## Coding Style & Naming Conventions

Follow existing formatting: four spaces in Python and two spaces in TypeScript/TSX. Use `snake_case` for Python modules and functions, `PascalCase` for React components and Pydantic/SQLAlchemy classes, and `camelCase` for TypeScript values. Keep API routes thin and move domain logic into services. Preserve client-generated UUIDs and idempotent sync behavior. Update `backend/app/catalogo_data.py` first, then regenerate the offline copy in `app/src/catalogo.ts` rather than editing both independently.

## Testing Guidelines

No automated test framework or coverage threshold is configured yet. Before submitting, run `npm run build`, exercise changed endpoints through `/api/docs` or `curl`, and verify relevant offline/sync behavior in the browser. For report changes, confirm generated PDF/HTML hashes match stored values. Never regenerate an existing report version.

## Commit & Pull Request Guidelines

Recent history uses concise Conventional Commit-style subjects such as `fix(sync): ...`, `feat(slides): ...`, and `docs: ...`. Keep each commit focused. Pull requests should explain the user-visible change, list validation performed, link related issues, and include screenshots for UI changes. Highlight schema, deployment, environment-variable, catalog, or report-integrity impacts explicitly; never commit secrets or populated `.env` files.
