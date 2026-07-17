"""Seed idempotente: crea el catálogo fijo y los usuarios iniciales.

Uso:  python -m app.seed
"""

from sqlalchemy.orm import Session

from app.catalogo_data import catalogo_rows
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.catalogo import CatalogoElemento
from app.models.user import User

# Usuarios iniciales (username, nombre completo, is_admin).
# Contraseña inicial = settings.SEED_PASSWORD para todos.
USUARIOS = [
    ("ldavila", "Leonardo Davila", False),
    ("smartinez", "Siomar Martinez", False),
    ("darao", "Daniel Arao", False),
    ("mlanz", "Mariana Lanz", False),
    ("frojas", "Felix Rojas", False),
    ("admin", "Administrador", True),
]


def seed_catalogo(db: Session) -> int:
    existentes = {c.codigo for c in db.query(CatalogoElemento.codigo).all()}
    nuevos = 0
    for row in catalogo_rows():
        if row["codigo"] in existentes:
            continue
        db.add(CatalogoElemento(**row))
        nuevos += 1
    db.commit()
    return nuevos


def seed_usuarios(db: Session) -> int:
    nuevos = 0
    for username, full_name, is_admin in USUARIOS:
        if db.query(User).filter(User.username == username).first():
            continue
        db.add(User(
            username=username,
            full_name=full_name,
            is_admin=is_admin,
            hashed_password=hash_password(settings.SEED_PASSWORD),
        ))
        nuevos += 1
    db.commit()
    return nuevos


def run() -> None:
    # create_all es seguro/idempotente; Alembic gestiona cambios posteriores.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        c = seed_catalogo(db)
        u = seed_usuarios(db)
        total = db.query(CatalogoElemento).count()
        print(f"Seed OK: catálogo +{c} (total {total}), usuarios +{u}.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
