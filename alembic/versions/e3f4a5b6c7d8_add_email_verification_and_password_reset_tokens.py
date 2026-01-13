"""add_email_verification_and_password_reset_tokens

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-01-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_token_table_if_missing(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name in inspector.get_table_names():
        return
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index(f"ix_{table_name}_user_id", table_name, ["user_id"])
    op.create_index(f"ix_{table_name}_token_hash", table_name, ["token_hash"])
    op.create_index(f"ix_{table_name}_issued_at", table_name, ["issued_at"])
    op.create_index(f"ix_{table_name}_expires_at", table_name, ["expires_at"])
    op.create_index(f"ix_{table_name}_used_at", table_name, ["used_at"])
    op.alter_column(table_name, "issued_at", server_default=None)


def upgrade() -> None:
    _create_token_table_if_missing("password_reset_tokens")
    _create_token_table_if_missing("email_verification_tokens")

    op.execute("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_issued_at ON password_reset_tokens (issued_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_expires_at ON password_reset_tokens (expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_used_at ON password_reset_tokens (used_at)")

    op.execute("CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_user_id ON email_verification_tokens (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_token_hash ON email_verification_tokens (token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_issued_at ON email_verification_tokens (issued_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_expires_at ON email_verification_tokens (expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_used_at ON email_verification_tokens (used_at)")


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_used_at", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_expires_at", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_issued_at", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_token_hash", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")

    op.drop_index("ix_password_reset_tokens_used_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_issued_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

