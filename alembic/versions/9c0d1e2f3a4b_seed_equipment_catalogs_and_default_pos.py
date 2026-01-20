"""seed equipment catalogs and default punto de venta

Revision ID: 9c0d1e2f3a4b
Revises: f9a0b1c2d3e4
Create Date: 2026-01-15
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "9c0d1e2f3a4b"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    now = datetime.utcnow()

    if "tipos_barril" in tables:
        default_barrels = [
            (20, "Barril 20L"),
            (30, "Barril 30L"),
            (50, "Barril 50L"),
            (100, "Barril 100L"),
        ]
        for capacidad, nombre in default_barrels:
            exists = bind.execute(
                sa.text("SELECT 1 FROM tipos_barril WHERE capacidad = :cap LIMIT 1"),
                {"cap": capacidad},
            ).scalar()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO tipos_barril (id_ext, capacidad, nombre) "
                        "VALUES (:id_ext, :capacidad, :nombre)"
                    ),
                    {"id_ext": uuid.uuid4(), "capacidad": capacidad, "nombre": nombre},
                )

    if "tipos_estado_equipo" in tables:
        default_states = [
            ("Activo", True),
            ("Inactivo", False),
            ("Mantenimiento", False),
        ]
        for estado, permite_ventas in default_states:
            exists = bind.execute(
                sa.text("SELECT 1 FROM tipos_estado_equipo WHERE estado = :estado LIMIT 1"),
                {"estado": estado},
            ).scalar()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO tipos_estado_equipo (id_ext, estado, permite_ventas) "
                        "VALUES (:id_ext, :estado, :permite_ventas)"
                    ),
                    {"id_ext": uuid.uuid4(), "estado": estado, "permite_ventas": permite_ventas},
                )

    if "tenants" in tables and "puntos_de_venta" in tables:
        tenants = bind.execute(sa.text("SELECT id FROM tenants")).fetchall()
        for (tenant_id,) in tenants:
            has_pv = bind.execute(
                sa.text("SELECT 1 FROM puntos_de_venta WHERE tenant_id = :t LIMIT 1"),
                {"t": tenant_id},
            ).scalar()
            if has_pv:
                continue
            bind.execute(
                sa.text(
                    "INSERT INTO puntos_de_venta "
                    "(id_ext, creado_el, creado_por, nombre, calle, altura, localidad, provincia, "
                    "codigo_postal, telefono, email, horario_apertura, horario_cierre, id_usuario_socio, tenant_id, activo) "
                    "VALUES "
                    "(:id_ext, :creado_el, NULL, :nombre, :calle, :altura, :localidad, :provincia, "
                    "NULL, NULL, NULL, NULL, NULL, NULL, :tenant_id, true)"
                ),
                {
                    "id_ext": uuid.uuid4(),
                    "creado_el": now,
                    "nombre": "Principal",
                    "calle": "Sin calle",
                    "altura": 1,
                    "localidad": "Sin localidad",
                    "provincia": "Sin provincia",
                    "tenant_id": tenant_id,
                },
            )


def downgrade() -> None:
    pass

