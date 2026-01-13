"""add_user_professional_info

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3c4d5e6
Create Date: 2026-01-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_professional_info" not in inspector.get_table_names():
        op.create_table(
            "user_professional_info",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False, unique=True),
            sa.Column("puesto", sa.String(length=100), nullable=True),
            sa.Column("departamento", sa.String(length=100), nullable=True),
            sa.Column("fecha_ingreso", sa.Date(), nullable=True),
            sa.Column("id_empleado", sa.String(length=50), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_user_professional_info_user_id", "user_professional_info", ["user_id"])
        op.create_index("ix_user_professional_info_updated_at", "user_professional_info", ["updated_at"])
        op.alter_column("user_professional_info", "updated_at", server_default=None)
    else:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_user_professional_info_user_id ON user_professional_info (user_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_user_professional_info_updated_at ON user_professional_info (updated_at)"
        )


def downgrade() -> None:
    op.drop_index("ix_user_professional_info_updated_at", table_name="user_professional_info")
    op.drop_index("ix_user_professional_info_user_id", table_name="user_professional_info")
    op.drop_table("user_professional_info")

