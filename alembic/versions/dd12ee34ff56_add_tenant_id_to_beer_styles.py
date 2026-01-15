"""add tenant id to beer styles

Revision ID: dd12ee34ff56
Revises: cc12dd34ee56
Create Date: 2026-01-15
"""

from alembic import op
import sqlalchemy as sa


revision = "dd12ee34ff56"
down_revision = "cc12dd34ee56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tipos_estilo_cerveza", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_tipos_estilo_cerveza_tenant_id"), "tipos_estilo_cerveza", ["tenant_id"], unique=False)
    op.create_foreign_key(
        "fk_tipos_estilo_cerveza_tenant_id_tenants",
        "tipos_estilo_cerveza",
        "tenants",
        ["tenant_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tipos_estilo_cerveza_tenant_id_tenants", "tipos_estilo_cerveza", type_="foreignkey")
    op.drop_index(op.f("ix_tipos_estilo_cerveza_tenant_id"), table_name="tipos_estilo_cerveza")
    op.drop_column("tipos_estilo_cerveza", "tenant_id")

