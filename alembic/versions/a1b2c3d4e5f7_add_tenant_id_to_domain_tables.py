"""add_tenant_id_to_domain_tables

Revision ID: a1b2c3d4e5f7
Revises: f1b2c3d4e5f6
Create Date: 2026-01-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "f1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "usuarios" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("usuarios")}
        if "tenant_id" not in cols:
            op.add_column("usuarios", sa.Column("tenant_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_usuarios_tenant_id_tenants",
                "usuarios",
                "tenants",
                ["tenant_id"],
                ["id"],
            )
            op.create_index("ix_usuarios_tenant_id", "usuarios", ["tenant_id"], unique=False)

        bind.execute(
            sa.text(
                "UPDATE usuarios u SET tenant_id = tu.tenant_id "
                "FROM tenant_users tu "
                "WHERE u.registrado_por = tu.user_id AND u.tenant_id IS NULL"
            )
        )

    if "cervezas" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("cervezas")}
        if "tenant_id" not in cols:
            op.add_column("cervezas", sa.Column("tenant_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_cervezas_tenant_id_tenants",
                "cervezas",
                "tenants",
                ["tenant_id"],
                ["id"],
            )
            op.create_index("ix_cervezas_tenant_id", "cervezas", ["tenant_id"], unique=False)

        bind.execute(
            sa.text(
                "UPDATE cervezas c SET tenant_id = tu.tenant_id "
                "FROM tenant_users tu "
                "WHERE c.creado_por = tu.user_id AND c.tenant_id IS NULL"
            )
        )

        index_names = {i["name"] for i in inspector.get_indexes("cervezas")}
        if "ix_cervezas_nombre" in index_names:
            op.drop_index("ix_cervezas_nombre", table_name="cervezas")
        if "ux_cervezas_tenant_nombre" not in index_names:
            op.create_index("ux_cervezas_tenant_nombre", "cervezas", ["tenant_id", "nombre"], unique=True)

    if "reglas_de_precio" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("reglas_de_precio")}
        if "tenant_id" not in cols:
            op.add_column("reglas_de_precio", sa.Column("tenant_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_reglas_de_precio_tenant_id_tenants",
                "reglas_de_precio",
                "tenants",
                ["tenant_id"],
                ["id"],
            )
            op.create_index("ix_reglas_de_precio_tenant_id", "reglas_de_precio", ["tenant_id"], unique=False)

        bind.execute(
            sa.text(
                "UPDATE reglas_de_precio r SET tenant_id = tu.tenant_id "
                "FROM tenant_users tu "
                "WHERE r.creado_por = tu.user_id AND r.tenant_id IS NULL"
            )
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if "reglas_de_precio" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("reglas_de_precio")}
        if "tenant_id" in cols:
            op.drop_index("ix_reglas_de_precio_tenant_id", table_name="reglas_de_precio")
            op.drop_constraint("fk_reglas_de_precio_tenant_id_tenants", "reglas_de_precio", type_="foreignkey")
            op.drop_column("reglas_de_precio", "tenant_id")

    if "cervezas" in inspector.get_table_names():
        index_names = {i["name"] for i in inspector.get_indexes("cervezas")}
        if "ux_cervezas_tenant_nombre" in index_names:
            op.drop_index("ux_cervezas_tenant_nombre", table_name="cervezas")
        if "ix_cervezas_nombre" not in index_names:
            op.create_index("ix_cervezas_nombre", "cervezas", ["nombre"], unique=True)

        cols = {c["name"] for c in inspector.get_columns("cervezas")}
        if "tenant_id" in cols:
            op.drop_index("ix_cervezas_tenant_id", table_name="cervezas")
            op.drop_constraint("fk_cervezas_tenant_id_tenants", "cervezas", type_="foreignkey")
            op.drop_column("cervezas", "tenant_id")

    if "usuarios" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("usuarios")}
        if "tenant_id" in cols:
            op.drop_index("ix_usuarios_tenant_id", table_name="usuarios")
            op.drop_constraint("fk_usuarios_tenant_id_tenants", "usuarios", type_="foreignkey")
            op.drop_column("usuarios", "tenant_id")
