"""add activo to equipos for soft delete

Revision ID: b1c2d3e4f5a6
Revises: 9c0d1e2f3a4b
Create Date: 2026-01-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "9c0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "equipos" not in inspector.get_table_names():
        return

    cols = {c["name"] for c in inspector.get_columns("equipos")}
    if "activo" in cols:
        return

    op.add_column("equipos", sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("equipos", "activo", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "equipos" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("equipos")}
    if "activo" not in cols:
        return
    op.drop_column("equipos", "activo")

