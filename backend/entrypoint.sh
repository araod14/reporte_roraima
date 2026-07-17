#!/bin/sh
set -e

echo "==> Esperando a PostgreSQL..."
python - <<'PY'
import os, time
import psycopg
url = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
for i in range(30):
    try:
        psycopg.connect(url).close()
        print("PostgreSQL disponible.")
        break
    except Exception as e:
        print(f"  intento {i+1}/30: {e}")
        time.sleep(2)
else:
    raise SystemExit("No se pudo conectar a PostgreSQL")
PY

echo "==> Aplicando migraciones (alembic upgrade head)..."
# Si aún no hay migraciones, seed.py hace create_all como respaldo.
alembic upgrade head || echo "  (sin migraciones aplicables; se usará create_all)"

echo "==> Ejecutando seed (idempotente)..."
python -m app.seed

echo "==> Iniciando servidor..."
exec "$@"
