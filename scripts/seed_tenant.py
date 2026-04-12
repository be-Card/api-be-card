"""
Script para crear un tenant de prueba con su usuario socio (owner),
punto de venta y equipo asociados. Útil para probar el kiosk.

Uso:
    uv run python scripts/seed_tenant.py
    uv run python scripts/seed_tenant.py --nombre "Mi Bar" --slug "mi-bar" --email "socio@mi-bar.com"
"""

import sys
import argparse
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from sqlmodel import Session, select
from app.core.database import engine
from app.core.config import settings
from app.models.user_extended import Usuario, TipoRolUsuario, UsuarioRol
from app.models.tenant import Tenant, TenantUser
from app.models.sales_point import PuntoVenta, Equipo
from app.services.tenants import TenantService


# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_NOMBRE = "Bar Test"
DEFAULT_SLUG   = "bar-test"
DEFAULT_EMAIL  = "socio@test.com"
DEFAULT_PASS   = "Test1234!"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_socio(session: Session, email: str, password: str) -> Usuario:
    existing = session.exec(select(Usuario).where(Usuario.email == email)).first()
    if existing:
        print(f"   ✅ Usuario ya existe: {email}")
        return existing

    # Derive a unique codigo_cliente from email
    codigo = "SOCIO-" + email.split("@")[0].upper()[:12]
    # Ensure uniqueness
    suffix = 1
    base = codigo
    while session.exec(select(Usuario).where(Usuario.codigo_cliente == codigo)).first():
        codigo = f"{base}-{suffix}"
        suffix += 1

    user = Usuario(
        nombre_usuario=email.split("@")[0],
        email=email,
        password_hash=hashlib.sha256(password.encode()).hexdigest(),
        nombres="Socio",
        apellidos="Test",
        codigo_cliente=codigo,
        tipo_registro="app",
        activo=True,
        verificado=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    print(f"   ✅ Usuario creado: {email}  (código: {codigo})")
    return user


def _assign_socio_role(session: Session, user: Usuario) -> None:
    rol = session.exec(
        select(TipoRolUsuario).where(TipoRolUsuario.tipo == "socio")
    ).first()
    if rol is None:
        print("   ⚠️  Rol 'socio' no encontrado, omitiendo asignación de rol.")
        return

    existing_role = session.exec(
        select(UsuarioRol)
        .where(UsuarioRol.id_usuario == user.id)
        .where(UsuarioRol.id_rol == rol.id)
        .where(UsuarioRol.fecha_revocacion.is_(None))
    ).first()
    if existing_role:
        return

    session.add(UsuarioRol(id_usuario=user.id, id_rol=rol.id))
    session.commit()
    print("   ✅ Rol 'socio' asignado")


def _get_or_create_tenant(
    session: Session,
    nombre: str,
    slug_base: str,
    owner: Usuario,
) -> Tenant:
    existing = TenantService.get_tenant_by_slug(session, slug_base)
    if existing:
        print(f"   ✅ Tenant ya existe: slug='{existing.slug}'")
        return existing

    tenant = TenantService.create_tenant(
        session,
        nombre=nombre,
        slug_base=slug_base,
        creado_por=owner.id,
        activo=True,
    )

    # Set a default subscription so it doesn't expire immediately
    now = datetime.utcnow()
    tenant.suscripcion_plan = "mensual"
    tenant.suscripcion_estado = "activa"
    tenant.suscripcion_hasta = now + timedelta(days=settings.subscription_default_days)
    tenant.suscripcion_gracia_hasta = (
        tenant.suscripcion_hasta + timedelta(days=settings.subscription_grace_days)
    )
    tenant.suscripcion_ultima_cobranza = now
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    TenantService.add_user_to_tenant(
        session, tenant_id=tenant.id, user_id=owner.id, rol="owner"
    )
    print(f"   ✅ Tenant creado: '{nombre}'  slug='{tenant.slug}'  id={tenant.id}")
    return tenant


def _ensure_equipo_linked_to_tenant(session: Session, tenant: Tenant) -> None:
    """Link the first existing equipo to this tenant if it has none yet."""
    from app.models.sales_point import TipoEstadoEquipo, TipoBarril

    # Grab the punto de venta for this tenant
    pv = session.exec(
        select(PuntoVenta).where(PuntoVenta.tenant_id == tenant.id).limit(1)
    ).first()
    if pv is None:
        print("   ⚠️  No hay punto de venta para este tenant.")
        return

    # Check if any equipo already linked to this tenant
    existing_eq = session.exec(
        select(Equipo).where(Equipo.tenant_id == tenant.id).limit(1)
    ).first()
    if existing_eq:
        print(f"   ✅ Equipo ya vinculado: '{existing_eq.nombre_equipo}'  id={existing_eq.id}  id_ext={existing_eq.id_ext}")
        return

    # Fall back to any unlinked equipo seeded by populate_initial_data
    unlinked = session.exec(
        select(Equipo).where(Equipo.tenant_id.is_(None)).limit(1)
    ).first()
    if unlinked:
        unlinked.tenant_id = tenant.id
        unlinked.id_punto_de_venta = pv.id
        session.add(unlinked)
        session.commit()
        session.refresh(unlinked)
        print(f"   ✅ Equipo vinculado al tenant: '{unlinked.nombre_equipo}'  id={unlinked.id}  id_ext={unlinked.id_ext}")
        return

    # Nothing to link
    print("   ℹ️  No hay equipos existentes para vincular. Ejecutá populate_initial_data.py primero.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Crear tenant de prueba para el kiosk")
    parser.add_argument("--nombre", default=DEFAULT_NOMBRE, help=f"Nombre del tenant (default: '{DEFAULT_NOMBRE}')")
    parser.add_argument("--slug",   default=DEFAULT_SLUG,   help=f"Slug del tenant (default: '{DEFAULT_SLUG}')")
    parser.add_argument("--email",  default=DEFAULT_EMAIL,  help=f"Email del usuario socio/owner (default: '{DEFAULT_EMAIL}')")
    parser.add_argument("--password", default=DEFAULT_PASS, help=f"Contraseña del socio (default: '{DEFAULT_PASS}')")
    args = parser.parse_args()

    print(f"\n🏗️  Creando tenant de prueba...")
    print(f"   nombre  : {args.nombre}")
    print(f"   slug    : {args.slug}")
    print(f"   owner   : {args.email}\n")

    try:
        tenant_slug = ""
        tenant_id = None
        with Session(engine) as session:
            print("👤 Usuario socio (owner):")
            socio = _get_or_create_socio(session, args.email, args.password)
            _assign_socio_role(session, socio)

            print("\n🏢 Tenant:")
            tenant = _get_or_create_tenant(session, args.nombre, args.slug, socio)
            tenant_slug = tenant.slug
            tenant_id = tenant.id

            print("\n🍺 Equipos:")
            _ensure_equipo_linked_to_tenant(session, tenant)

        print("\n🎉 Tenant listo!\n")
        print("   Para usar en requests:")
        print("     X-Tenant-Slug:", tenant_slug)
        print("     Tenant ID    :", tenant_id)
        print(f"   Login socio: {args.email} / {args.password}")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
