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

echo "==> Inicializando o migrando base de datos..."
python -m app.bootstrap

echo "==> Iniciando servidor..."
exec "$@"
