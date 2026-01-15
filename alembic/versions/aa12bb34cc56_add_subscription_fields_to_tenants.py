"""add subscription fields to tenants

Revision ID: aa12bb34cc56
Revises: f1b2c3d4e5f6
Create Date: 2026-01-15
"""

from alembic import op
import sqlalchemy as sa


revision = "aa12bb34cc56"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("suscripcion_plan", sa.String(length=30), nullable=False, server_default="mensual"))
    op.add_column("tenants", sa.Column("suscripcion_estado", sa.String(length=20), nullable=False, server_default="activa"))
    op.add_column("tenants", sa.Column("suscripcion_hasta", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column("suscripcion_gracia_hasta", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column("suscripcion_ultima_cobranza", sa.DateTime(), nullable=True))

    op.create_index(op.f("ix_tenants_suscripcion_estado"), "tenants", ["suscripcion_estado"], unique=False)
    op.create_index(op.f("ix_tenants_suscripcion_hasta"), "tenants", ["suscripcion_hasta"], unique=False)
    op.create_index(op.f("ix_tenants_suscripcion_gracia_hasta"), "tenants", ["suscripcion_gracia_hasta"], unique=False)

    op.alter_column("tenants", "suscripcion_plan", server_default=None)
    op.alter_column("tenants", "suscripcion_estado", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_suscripcion_gracia_hasta"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_suscripcion_hasta"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_suscripcion_estado"), table_name="tenants")

    op.drop_column("tenants", "suscripcion_ultima_cobranza")
    op.drop_column("tenants", "suscripcion_gracia_hasta")
    op.drop_column("tenants", "suscripcion_hasta")
    op.drop_column("tenants", "suscripcion_estado")
    op.drop_column("tenants", "suscripcion_plan")

