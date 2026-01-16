"""seed superadmin admin@becard.com.ar

Revision ID: f9a0b1c2d3e4
Revises: ee12ff34aa56
Create Date: 2026-01-15
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
import bcrypt


revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "ee12ff34aa56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hash_password(password: str) -> str:
    password_bytes = (password or "").encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "usuarios" not in tables or "tipos_rol_usuario" not in tables or "usuarios_roles" not in tables:
        return

    admin_email = "admin@becard.com.ar"
    admin_password = "beCard2026."
    now = datetime.utcnow()

    role_id = bind.execute(
        sa.text("SELECT id FROM tipos_rol_usuario WHERE tipo = :tipo LIMIT 1"),
        {"tipo": "superadmin"},
    ).scalar()
    if role_id is None:
        bind.execute(
            sa.text(
                "INSERT INTO tipos_rol_usuario (id_ext, creado_el, tipo, descripcion) "
                "VALUES (:id_ext, :creado_el, :tipo, :descripcion)"
            ),
            {
                "id_ext": uuid.uuid4(),
                "creado_el": now,
                "tipo": "superadmin",
                "descripcion": "Acceso total al panel de administración",
            },
        )
        role_id = bind.execute(
            sa.text("SELECT id FROM tipos_rol_usuario WHERE tipo = :tipo LIMIT 1"),
            {"tipo": "superadmin"},
        ).scalar()

    if role_id is None:
        return

    user_id = bind.execute(
        sa.text("SELECT id FROM usuarios WHERE email = :email LIMIT 1"),
        {"email": admin_email},
    ).scalar()

    password_hash = _hash_password(admin_password)

    if user_id is None:
        base_username = "admin_becard"
        username = base_username
        username_taken = bind.execute(
            sa.text("SELECT 1 FROM usuarios WHERE nombre_usuario = :u LIMIT 1"),
            {"u": username},
        ).scalar()
        if username_taken:
            username = f"{base_username}_2026"

        base_codigo = "BC-ADMIN-2026"
        codigo_cliente = base_codigo
        codigo_taken = bind.execute(
            sa.text("SELECT 1 FROM usuarios WHERE codigo_cliente = :c LIMIT 1"),
            {"c": codigo_cliente},
        ).scalar()
        if codigo_taken:
            codigo_cliente = f"{base_codigo}-{uuid.uuid4().hex[:6].upper()}"

        bind.execute(
            sa.text(
                "INSERT INTO usuarios "
                "(id_ext, nombre_usuario, codigo_cliente, nombres, apellidos, email, password_hash, password_salt, "
                "tipo_registro, fecha_creacion, activo, verificado, intentos_login_fallidos) "
                "VALUES "
                "(:id_ext, :nombre_usuario, :codigo_cliente, :nombres, :apellidos, :email, :password_hash, :password_salt, "
                ":tipo_registro, :fecha_creacion, :activo, :verificado, :intentos_login_fallidos)"
            ),
            {
                "id_ext": uuid.uuid4(),
                "nombre_usuario": username,
                "codigo_cliente": codigo_cliente,
                "nombres": "Admin",
                "apellidos": "BeCard",
                "email": admin_email,
                "password_hash": password_hash,
                "password_salt": "",
                "tipo_registro": "app",
                "fecha_creacion": now,
                "activo": True,
                "verificado": True,
                "intentos_login_fallidos": 0,
            },
        )
        user_id = bind.execute(
            sa.text("SELECT id FROM usuarios WHERE email = :email LIMIT 1"),
            {"email": admin_email},
        ).scalar()
    else:
        bind.execute(
            sa.text(
                "UPDATE usuarios "
                "SET password_hash = :password_hash, password_salt = :password_salt, activo = true, verificado = true "
                "WHERE id = :id"
            ),
            {"password_hash": password_hash, "password_salt": "", "id": user_id},
        )

    if user_id is None:
        return

    existing_role = bind.execute(
        sa.text(
            "SELECT fecha_revocacion FROM usuarios_roles "
            "WHERE id_usuario = :user_id AND id_rol = :role_id LIMIT 1"
        ),
        {"user_id": user_id, "role_id": role_id},
    ).fetchone()

    if existing_role is None:
        bind.execute(
            sa.text(
                "INSERT INTO usuarios_roles (id_usuario, id_rol, fecha_asignacion, asignado_por, fecha_revocacion) "
                "VALUES (:user_id, :role_id, :fecha_asignacion, NULL, NULL)"
            ),
            {"user_id": user_id, "role_id": role_id, "fecha_asignacion": now},
        )
    else:
        revoked_at = existing_role[0]
        if revoked_at is not None:
            bind.execute(
                sa.text(
                    "UPDATE usuarios_roles "
                    "SET fecha_revocacion = NULL, fecha_asignacion = :fecha_asignacion "
                    "WHERE id_usuario = :user_id AND id_rol = :role_id"
                ),
                {"fecha_asignacion": now, "user_id": user_id, "role_id": role_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "usuarios" not in tables or "tipos_rol_usuario" not in tables or "usuarios_roles" not in tables:
        return

    admin_email = "admin@becard.com.ar"
    user_id = bind.execute(
        sa.text("SELECT id FROM usuarios WHERE email = :email LIMIT 1"),
        {"email": admin_email},
    ).scalar()
    role_id = bind.execute(
        sa.text("SELECT id FROM tipos_rol_usuario WHERE tipo = :tipo LIMIT 1"),
        {"tipo": "superadmin"},
    ).scalar()

    if user_id is not None and role_id is not None:
        bind.execute(
            sa.text("DELETE FROM usuarios_roles WHERE id_usuario = :u AND id_rol = :r"),
            {"u": user_id, "r": role_id},
        )
