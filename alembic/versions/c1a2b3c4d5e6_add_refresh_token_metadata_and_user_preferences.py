"""add_refresh_token_metadata_and_user_preferences

Revision ID: c1a2b3c4d5e6
Revises: b3c1f9d2a1e7
Create Date: 2026-01-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a2b3c4d5e6"
down_revision: Union[str, None] = "b3c1f9d2a1e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "refresh_tokens" in inspector.get_table_names():
        refresh_cols = {c["name"] for c in inspector.get_columns("refresh_tokens")}
        if "user_agent" not in refresh_cols:
            op.add_column("refresh_tokens", sa.Column("user_agent", sa.String(length=512), nullable=True))
        if "ip_address" not in refresh_cols:
            op.add_column("refresh_tokens", sa.Column("ip_address", sa.String(length=64), nullable=True))

    if "user_preferences" not in inspector.get_table_names():
        op.create_table(
            "user_preferences",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False, unique=True),
            sa.Column("notifications_email_sales", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("notifications_email_inventory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("notifications_email_clients", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("notifications_push_critical", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("notifications_push_reports", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("language", sa.String(length=5), nullable=False, server_default="es"),
            sa.Column("date_format", sa.String(length=20), nullable=False, server_default="YYYY-MM-DD"),
            sa.Column("theme", sa.String(length=20), nullable=False, server_default="dark"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])

        op.alter_column("user_preferences", "notifications_email_sales", server_default=None)
        op.alter_column("user_preferences", "notifications_email_inventory", server_default=None)
        op.alter_column("user_preferences", "notifications_email_clients", server_default=None)
        op.alter_column("user_preferences", "notifications_push_critical", server_default=None)
        op.alter_column("user_preferences", "notifications_push_reports", server_default=None)
        op.alter_column("user_preferences", "language", server_default=None)
        op.alter_column("user_preferences", "date_format", server_default=None)
        op.alter_column("user_preferences", "theme", server_default=None)
        op.alter_column("user_preferences", "updated_at", server_default=None)
    else:
        op.execute("CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id ON user_preferences (user_id)")


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")

    op.drop_column("refresh_tokens", "ip_address")
    op.drop_column("refresh_tokens", "user_agent")
