"""add tenant payments and plan fields

Revision ID: bb12cc34dd56
Revises: aa12bb34cc56
Create Date: 2026-01-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "bb12cc34dd56"
down_revision = "aa12bb34cc56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("suscripcion_precio_centavos", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("suscripcion_moneda", sa.String(length=10), nullable=False, server_default="ARS"),
    )
    op.add_column(
        "tenants",
        sa.Column("suscripcion_periodo_dias", sa.Integer(), nullable=False, server_default="30"),
    )
    op.alter_column("tenants", "suscripcion_precio_centavos", server_default=None)
    op.alter_column("tenants", "suscripcion_moneda", server_default=None)
    op.alter_column("tenants", "suscripcion_periodo_dias", server_default=None)

    inspector = inspect(op.get_bind())
    has_tenant_payments = "tenant_payments" in inspector.get_table_names()

    if not has_tenant_payments:
        op.create_table(
            "tenant_payments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("id_ext", sa.Uuid(), nullable=False),
            sa.Column("creado_el", sa.DateTime(), nullable=False),
            sa.Column("creado_por", sa.Integer(), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("amount_centavos", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("paid_at", sa.DateTime(), nullable=False),
            sa.Column("period_start", sa.DateTime(), nullable=True),
            sa.Column("period_end", sa.DateTime(), nullable=True),
            sa.Column("provider", sa.String(length=30), nullable=True),
            sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
            sa.ForeignKeyConstraint(["creado_por"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("id_ext"),
        )

    op.create_index(op.f("ix_tenant_payments_id_ext"), "tenant_payments", ["id_ext"], unique=False, if_not_exists=True)
    op.create_index(op.f("ix_tenant_payments_paid_at"), "tenant_payments", ["paid_at"], unique=False, if_not_exists=True)
    op.create_index(op.f("ix_tenant_payments_period_end"), "tenant_payments", ["period_end"], unique=False, if_not_exists=True)
    op.create_index(op.f("ix_tenant_payments_period_start"), "tenant_payments", ["period_start"], unique=False, if_not_exists=True)
    op.create_index(op.f("ix_tenant_payments_provider_payment_id"), "tenant_payments", ["provider_payment_id"], unique=False, if_not_exists=True)
    op.create_index(op.f("ix_tenant_payments_status"), "tenant_payments", ["status"], unique=False, if_not_exists=True)
    op.create_index(op.f("ix_tenant_payments_tenant_id"), "tenant_payments", ["tenant_id"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenant_payments_tenant_id"), table_name="tenant_payments")
    op.drop_index(op.f("ix_tenant_payments_status"), table_name="tenant_payments")
    op.drop_index(op.f("ix_tenant_payments_provider_payment_id"), table_name="tenant_payments")
    op.drop_index(op.f("ix_tenant_payments_period_start"), table_name="tenant_payments")
    op.drop_index(op.f("ix_tenant_payments_period_end"), table_name="tenant_payments")
    op.drop_index(op.f("ix_tenant_payments_paid_at"), table_name="tenant_payments")
    op.drop_index(op.f("ix_tenant_payments_id_ext"), table_name="tenant_payments")
    op.drop_table("tenant_payments")

    op.drop_column("tenants", "suscripcion_periodo_dias")
    op.drop_column("tenants", "suscripcion_moneda")
    op.drop_column("tenants", "suscripcion_precio_centavos")
