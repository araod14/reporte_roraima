"""Initialize a fresh database or migrate an existing installation."""
import subprocess
from sqlalchemy import inspect

from app.db.base import Base
from app.db.session import engine
from app.seed import run as seed
import app.models  # noqa: F401


def main():
    tables = set(inspect(engine).get_table_names())
    if "users" not in tables:
        # The historical first migration only creates diarios and assumes
        # seed-created users. A fresh database needs the full model schema.
        seed()
        subprocess.run(["alembic", "stamp", "head"], check=True)
    elif "alembic_version" not in tables and set(Base.metadata.tables).issubset(tables):
        # Old seed-only installations already have every model table.
        subprocess.run(["alembic", "stamp", "head"], check=True)
        seed()
    else:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        seed()


if __name__ == "__main__":
    main()
