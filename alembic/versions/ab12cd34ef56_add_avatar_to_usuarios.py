"""add avatar to usuarios

Revision ID: ab12cd34ef56
Revises: f9a0b1c2d3e4
Create Date: 2026-01-16
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab12cd34ef56"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("usuarios")} if "usuarios" in inspector.get_table_names() else set()
    if "usuarios" not in inspector.get_table_names() or "avatar" in columns:
        return
    op.add_column("usuarios", sa.Column("avatar", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("usuarios")} if "usuarios" in inspector.get_table_names() else set()
    if "usuarios" not in inspector.get_table_names() or "avatar" not in columns:
        return
    op.drop_column("usuarios", "avatar")

