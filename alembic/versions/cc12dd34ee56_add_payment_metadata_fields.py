"""add payment metadata fields

Revision ID: cc12dd34ee56
Revises: bb12cc34dd56
Create Date: 2026-01-15
"""

from alembic import op
import sqlalchemy as sa


revision = "cc12dd34ee56"
down_revision = "bb12cc34dd56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_payments", sa.Column("payment_method", sa.String(length=30), nullable=True))
    op.add_column("tenant_payments", sa.Column("notes", sa.String(length=500), nullable=True))
    op.add_column("tenant_payments", sa.Column("failure_reason", sa.String(length=200), nullable=True))
    op.add_column("tenant_payments", sa.Column("refunded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant_payments", "refunded_at")
    op.drop_column("tenant_payments", "failure_reason")
    op.drop_column("tenant_payments", "notes")
    op.drop_column("tenant_payments", "payment_method")

