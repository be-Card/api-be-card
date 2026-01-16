"""add stock_base to cervezas

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-01-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cervezas" not in inspector.get_table_names():
        return

    cols = {c["name"] for c in inspector.get_columns("cervezas")}
    if "stock_base" in cols:
        return

    op.add_column("cervezas", sa.Column("stock_base", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.alter_column("cervezas", "stock_base", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cervezas" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("cervezas")}
    if "stock_base" not in cols:
        return
    op.drop_column("cervezas", "stock_base")

