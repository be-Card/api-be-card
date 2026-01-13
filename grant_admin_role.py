#!/usr/bin/env python3
"""
Script utilitario para asignar el rol 'admin' a un usuario administrador.

Busca un usuario admin por email (admin@becard.com o admin@gmail.com) y
asegura que el rol 'admin' exista, luego lo asigna si no está asignado.
"""
import sys
from pathlib import Path

# Añadir la raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user_extended import Usuario, TipoRolUsuario, UsuarioRol


def grant_admin_role():
    with Session(engine) as session:
        # Asegurar que el rol 'admin' exista
        admin_role = session.exec(select(TipoRolUsuario).where(TipoRolUsuario.tipo == "admin")).first()
        if not admin_role:
            admin_role = TipoRolUsuario(tipo="admin", descripcion="Administrador del sistema")
            session.add(admin_role)
            session.commit()
            session.refresh(admin_role)
            print(f"✅ Rol 'admin' creado (id={admin_role.id})")
        else:
            print(f"ℹ️ Rol 'admin' ya existe (id={admin_role.id})")

        # Buscar usuario admin por email
        admin_user = (
            session.exec(select(Usuario).where(Usuario.email == "admin@becard.com")).first()
            or session.exec(select(Usuario).where(Usuario.email == "admin@gmail.com")).first()
        )
        if not admin_user:
            print("❌ No se encontró usuario admin (admin@becard.com ni admin@gmail.com).")
            print("   Crea uno con scripts/simple_seed.py o add_gmail_admin.py y vuelve a ejecutar.")
            return

        print(f"👤 Usuario admin encontrado: id={admin_user.id}, email={admin_user.email}")

        # Verificar si ya tiene el rol asignado activo
        existing = session.exec(
            select(UsuarioRol).where(
                UsuarioRol.id_usuario == admin_user.id,
                UsuarioRol.id_rol == admin_role.id,
                UsuarioRol.fecha_revocacion == None,
            )
        ).first()

        if existing:
            print("✅ El usuario ya tiene rol 'admin' activo.")
            return

        # Asignar rol
        usuario_rol = UsuarioRol(
            id_usuario=admin_user.id,
            id_rol=admin_role.id,
            asignado_por=admin_user.id,
        )
        session.add(usuario_rol)
        session.commit()
        print("🎉 Rol 'admin' asignado exitosamente al usuario.")


if __name__ == "__main__":
    grant_admin_role()