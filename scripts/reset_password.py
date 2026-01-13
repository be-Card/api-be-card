#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from sqlmodel import Session, select

from app.core.database import engine
from app.core.security import get_password_hash
from app.models.user_extended import Usuario


def main() -> int:
    parser = argparse.ArgumentParser(description="Resetear password de un usuario por email")
    parser.add_argument("--email", required=True, help="Email del usuario")
    parser.add_argument("--password", required=True, help="Nueva contraseña")
    args = parser.parse_args()

    email = args.email.strip().lower()

    with Session(engine) as session:
        user = session.exec(select(Usuario).where(Usuario.email == email)).first()
        if not user:
            print(f"❌ Usuario no encontrado: {email}")
            return 1

        user.password_hash = get_password_hash(args.password)
        user.password_salt = ""
        user.intentos_login_fallidos = 0
        user.bloqueado_hasta = None
        user.activo = True

        session.add(user)
        session.commit()

    print(f"✅ Password actualizado para {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

