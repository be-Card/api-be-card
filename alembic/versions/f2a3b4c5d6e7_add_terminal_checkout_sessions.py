"""add terminal checkout sessions

Revision ID: f2a3b4c5d6e7
Revises: ee12ff34aa56
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa


revision = "f2a3b4c5d6e7"
down_revision = "ee12ff34aa56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "terminal_checkout_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_ext", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("terminal_id", sa.Integer(), nullable=False),
        sa.Column("equipo_id", sa.Integer(), nullable=False),
        sa.Column("cerveza_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payment_provider", sa.String(length=40), nullable=False),
        sa.Column("terminal_nombre", sa.String(length=100), nullable=False),
        sa.Column("cerveza_nombre", sa.String(length=80), nullable=False),
        sa.Column("cerveza_tipo", sa.String(length=50), nullable=True),
        sa.Column("price_per_liter", sa.Numeric(10, 2), nullable=False),
        sa.Column("requested_ml", sa.Integer(), nullable=True),
        sa.Column("requested_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("checkout_url", sa.String(length=500), nullable=False),
        sa.Column("mercadopago_qr_data", sa.Text(), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("command_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["terminal_id"], ["terminales_registro.id"]),
        sa.ForeignKeyConstraint(["equipo_id"], ["equipos.id"]),
        sa.ForeignKeyConstraint(["cerveza_id"], ["cervezas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_terminal_checkout_sessions_id_ext",
        "terminal_checkout_sessions",
        ["id_ext"],
        unique=True,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_tenant_id",
        "terminal_checkout_sessions",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_terminal_id",
        "terminal_checkout_sessions",
        ["terminal_id"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_equipo_id",
        "terminal_checkout_sessions",
        ["equipo_id"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_cerveza_id",
        "terminal_checkout_sessions",
        ["cerveza_id"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_status",
        "terminal_checkout_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_provider_payment_id",
        "terminal_checkout_sessions",
        ["provider_payment_id"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_expires_at",
        "terminal_checkout_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_approved_at",
        "terminal_checkout_sessions",
        ["approved_at"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_command_sent_at",
        "terminal_checkout_sessions",
        ["command_sent_at"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_created_at",
        "terminal_checkout_sessions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_terminal_checkout_sessions_updated_at",
        "terminal_checkout_sessions",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_terminal_checkout_sessions_updated_at", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_created_at", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_command_sent_at", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_approved_at", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_expires_at", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_provider_payment_id", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_status", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_cerveza_id", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_equipo_id", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_terminal_id", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_tenant_id", table_name="terminal_checkout_sessions")
    op.drop_index("ix_terminal_checkout_sessions_id_ext", table_name="terminal_checkout_sessions")
    op.drop_table("terminal_checkout_sessions")
