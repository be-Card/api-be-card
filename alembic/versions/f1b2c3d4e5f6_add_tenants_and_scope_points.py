"""add_tenants_and_scope_points

Revision ID: f1b2c3d4e5f6
Revises: e3f4a5b6c7d8
Create Date: 2026-01-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid
import sqlmodel


revision: str = "f1b2c3d4e5f6"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    slug = []
    prev_dash = False
    for ch in value:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            slug.append(ch)
            prev_dash = False
            continue
        if not prev_dash:
            slug.append("-")
            prev_dash = True
    out = "".join(slug).strip("-")
    return (out[:80] or "tenant").strip("-")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "tenants" not in inspector.get_table_names():
        op.create_table(
            "tenants",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("id_ext", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("creado_el", sa.DateTime(), nullable=False),
            sa.Column("creado_por", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("nombre", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_tenants_id_ext", "tenants", ["id_ext"], unique=True)
        op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
        op.create_index("ix_tenants_activo", "tenants", ["activo"], unique=False)
        op.alter_column("tenants", "activo", server_default=None)

    if "tenant_users" not in inspector.get_table_names():
        op.create_table(
            "tenant_users",
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), primary_key=True, nullable=False),
            sa.Column("rol", sa.String(length=30), nullable=False, server_default="member"),
            sa.Column("creado_el", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_tenant_users_user_id", "tenant_users", ["user_id"], unique=False)
        op.alter_column("tenant_users", "rol", server_default=None)
        op.alter_column("tenant_users", "creado_el", server_default=None)

    pv_cols = {c["name"] for c in inspector.get_columns("puntos_de_venta")}
    if "tenant_id" not in pv_cols:
        op.add_column("puntos_de_venta", sa.Column("tenant_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_puntos_de_venta_tenant_id_tenants",
            "puntos_de_venta",
            "tenants",
            ["tenant_id"],
            ["id"],
        )
        op.create_index("ix_puntos_de_venta_tenant_id", "puntos_de_venta", ["tenant_id"], unique=False)

    tenants_exist = "tenants" in inspector.get_table_names()
    pv_has_tenant = "tenant_id" in {c["name"] for c in inspector.get_columns("puntos_de_venta")}
    if tenants_exist and pv_has_tenant:
        res = bind.execute(
            sa.text(
                "SELECT DISTINCT id_usuario_socio FROM puntos_de_venta WHERE id_usuario_socio IS NOT NULL"
            )
        )
        socio_ids = [row[0] for row in res.fetchall()]

        for socio_id in socio_ids:
            existing_tenant_id = bind.execute(
                sa.text(
                    "SELECT id FROM tenants WHERE creado_por = :socio_id ORDER BY id LIMIT 1"
                ),
                {"socio_id": socio_id},
            ).scalar()

            if existing_tenant_id is None:
                socio_email = bind.execute(
                    sa.text("SELECT email FROM usuarios WHERE id = :socio_id"),
                    {"socio_id": socio_id},
                ).scalar()
                pv_name = bind.execute(
                    sa.text(
                        "SELECT nombre FROM puntos_de_venta WHERE id_usuario_socio = :socio_id ORDER BY id LIMIT 1"
                    ),
                    {"socio_id": socio_id},
                ).scalar()

                base_name = pv_name or (socio_email or f"Cuenta {socio_id}")
                slug_base = (socio_email or base_name).split("@", 1)[0]
                slug = _slugify(slug_base)
                slug = f"{slug}-{socio_id}"

                created_tenant_id = bind.execute(
                    sa.text(
                        "INSERT INTO tenants (id_ext, creado_el, creado_por, nombre, slug, activo) "
                        "VALUES (:id_ext, now(), :socio_id, :nombre, :slug, true) "
                        "RETURNING id"
                    ),
                    {"id_ext": uuid.uuid4(), "socio_id": socio_id, "nombre": base_name, "slug": slug},
                ).scalar()

                bind.execute(
                    sa.text(
                        "INSERT INTO tenant_users (tenant_id, user_id, rol, creado_el) "
                        "VALUES (:tenant_id, :user_id, 'owner', now()) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"tenant_id": created_tenant_id, "user_id": socio_id},
                )
                tenant_id = created_tenant_id
            else:
                tenant_id = existing_tenant_id

            bind.execute(
                sa.text(
                    "UPDATE puntos_de_venta SET tenant_id = :tenant_id "
                    "WHERE id_usuario_socio = :socio_id AND tenant_id IS NULL"
                ),
                {"tenant_id": tenant_id, "socio_id": socio_id},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "puntos_de_venta" in inspector.get_table_names():
        pv_cols = {c["name"] for c in inspector.get_columns("puntos_de_venta")}
        if "tenant_id" in pv_cols:
            op.drop_index("ix_puntos_de_venta_tenant_id", table_name="puntos_de_venta")
            op.drop_constraint("fk_puntos_de_venta_tenant_id_tenants", "puntos_de_venta", type_="foreignkey")
            op.drop_column("puntos_de_venta", "tenant_id")

    if "tenant_users" in inspector.get_table_names():
        op.drop_index("ix_tenant_users_user_id", table_name="tenant_users")
        op.drop_table("tenant_users")

    if "tenants" in inspector.get_table_names():
        op.drop_index("ix_tenants_activo", table_name="tenants")
        op.drop_index("ix_tenants_slug", table_name="tenants")
        op.drop_index("ix_tenants_id_ext", table_name="tenants")
        op.drop_table("tenants")
