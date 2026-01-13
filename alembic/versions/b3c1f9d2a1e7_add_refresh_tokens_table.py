"""add_refresh_tokens_table

Revision ID: b3c1f9d2a1e7
Revises: 8597f4da69e3
Create Date: 2026-01-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3c1f9d2a1e7"
down_revision: Union[str, None] = "8597f4da69e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "refresh_tokens" not in inspector.get_table_names():
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False, unique=True),
            sa.Column("jti", sa.String(length=64), nullable=False, unique=True),
            sa.Column("issued_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("replaced_by_token_hash", sa.String(length=128), nullable=True),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
        op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"])
        op.create_index("ix_refresh_tokens_issued_at", "refresh_tokens", ["issued_at"])
        op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
        op.create_index("ix_refresh_tokens_revoked_at", "refresh_tokens", ["revoked_at"])
        return

    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens (token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_jti ON refresh_tokens (jti)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_issued_at ON refresh_tokens (issued_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at ON refresh_tokens (expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_revoked_at ON refresh_tokens (revoked_at)")


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_revoked_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_issued_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_jti", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
