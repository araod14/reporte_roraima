"""Gestión de usuarios por línea de comandos.

Ejemplos (dentro del contenedor api):
  python -m scripts.manage_users list
  python -m scripts.manage_users add jperez "Juan Perez" --password Clave123
  python -m scripts.manage_users passwd darao --password NuevaClave
  python -m scripts.manage_users rename darao --full-name "Daniel Arao R."
  python -m scripts.manage_users delete jperez
"""

import argparse
import sys

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestión de usuarios")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    p_add = sub.add_parser("add")
    p_add.add_argument("username")
    p_add.add_argument("full_name")
    p_add.add_argument("--password", default=settings.SEED_PASSWORD)
    p_add.add_argument("--admin", action="store_true")

    p_pw = sub.add_parser("passwd")
    p_pw.add_argument("username")
    p_pw.add_argument("--password", required=True)

    p_rn = sub.add_parser("rename")
    p_rn.add_argument("username")
    p_rn.add_argument("--full-name", required=True)

    p_del = sub.add_parser("delete")
    p_del.add_argument("username")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "list":
            for u in db.query(User).order_by(User.username).all():
                flag = " [admin]" if u.is_admin else ""
                print(f"{u.username:12} {u.full_name}{flag}")
            return 0

        if args.cmd == "add":
            if db.query(User).filter(User.username == args.username).first():
                print(f"Ya existe: {args.username}", file=sys.stderr)
                return 1
            db.add(User(
                username=args.username,
                full_name=args.full_name,
                is_admin=args.admin,
                hashed_password=hash_password(args.password),
            ))
            db.commit()
            print(f"Creado: {args.username}")
            return 0

        user = db.query(User).filter(User.username == args.username).first()
        if not user:
            print(f"No existe: {args.username}", file=sys.stderr)
            return 1

        if args.cmd == "passwd":
            user.hashed_password = hash_password(args.password)
            db.commit()
            print(f"Contraseña actualizada: {args.username}")
        elif args.cmd == "rename":
            user.full_name = args.full_name
            db.commit()
            print(f"Renombrado: {args.username} -> {args.full_name}")
        elif args.cmd == "delete":
            db.delete(user)
            db.commit()
            print(f"Eliminado: {args.username}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
