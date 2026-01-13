#!/usr/bin/env python3
"""
Script utilitario para asignar el rol 'socio' a un usuario específico.

Busca un usuario por su email (cliente@demo.com) y asegura que el rol 'socio' exista,
luego lo asigna si no está ya asignado.
"""
import sys
from pathlib import Path

# Añadir la raíz del proyecto al sys.path
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user_extended import Usuario, TipoRolUsuario, UsuarioRol

USER_EMAIL = "cliente@demo.com"
ROLE_NAME = "socio"

def grant_socio_role():
    with Session(engine) as session:
        # 1. Asegurar que el rol 'socio' exista
        socio_role = session.exec(select(TipoRolUsuario).where(TipoRolUsuario.tipo == ROLE_NAME)).first()
        if not socio_role:
            socio_role = TipoRolUsuario(tipo=ROLE_NAME, descripcion="Socio de BeCard")
            session.add(socio_role)
            session.commit()
            session.refresh(socio_role)
            print(f"✅ Rol '{ROLE_NAME}' creado (id={socio_role.id})")
        else:
            print(f"ℹ️ Rol '{ROLE_NAME}' ya existe (id={socio_role.id})")

        # 2. Buscar usuario por email
        user = session.exec(select(Usuario).where(Usuario.email == USER_EMAIL)).first()
        if not user:
            print(f"❌ No se encontró el usuario con email '{USER_EMAIL}'.")
            print("   Asegúrate de que el usuario exista en la base de datos.")
            return

        print(f"👤 Usuario encontrado: id={user.id}, email={user.email}")

        # 3. Verificar si ya tiene el rol asignado y activo
        existing_role = session.exec(
            select(UsuarioRol).where(
                UsuarioRol.id_usuario == user.id,
                UsuarioRol.id_rol == socio_role.id,
                UsuarioRol.fecha_revocacion == None,  # Rol activo
            )
        ).first()

        if existing_role:
            print(f"✅ El usuario ya tiene el rol '{ROLE_NAME}' activo.")
            return

        # 4. Asignar el rol
        # Para la asignación, necesitamos un admin que realice la acción. Usaremos el primer admin que encontremos.
        admin_assigner = session.exec(select(Usuario).where(Usuario.email.like('%admin%'))).first()
        if not admin_assigner:
            print("❌ No se encontró un usuario administrador para realizar la asignación.")
            return

        usuario_rol = UsuarioRol(
            id_usuario=user.id,
            id_rol=socio_role.id,
            asignado_por=admin_assigner.id, # El rol es asignado por un admin
        )
        session.add(usuario_rol)
        session.commit()
        print(f"🎉 Rol '{ROLE_NAME}' asignado exitosamente al usuario '{USER_EMAIL}'.")

if __name__ == "__main__":
    grant_socio_role()