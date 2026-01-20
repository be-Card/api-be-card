from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel

from app.core.database import get_session
from app.core.config import settings
from app.models.tenant import Tenant
from app.models.user_extended import Usuario
from app.routers.auth import get_current_active_user, require_admin
from app.services.users import UserService
from app.services.tenants import TenantService


router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantRead(SQLModel):
    id: int
    id_ext: str
    nombre: str
    slug: str


class AdminCreateTenantRequest(SQLModel):
    nombre: str
    slug_base: Optional[str] = None
    owner_email: str
    owner_rol: str = "owner"
    activo: bool = True


class AdminTenantMembershipRequest(SQLModel):
    user_email: str
    rol: str = "member"


@router.get("/me", response_model=List[TenantRead])
def get_my_tenants(
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    tenants = TenantService.get_tenants_for_user(session, current_user.id)
    return [
        TenantRead(
            id=t.id,
            id_ext=str(t.id_ext),
            nombre=t.nombre,
            slug=t.slug,
        )
        for t in tenants
    ]


@router.post("/admin", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def admin_create_tenant(
    payload: AdminCreateTenantRequest,
    session: Session = Depends(get_session),
    admin_user: Usuario = Depends(require_admin),
):
    owner = UserService.get_user_by_email(session, payload.owner_email)
    if owner is None:
        raise HTTPException(
            status_code=404,
            detail="Usuario dueño no encontrado. Primero registrá el usuario (y verificá su email) o asignalo luego como miembro.",
        )

    slug_base = (payload.slug_base or payload.nombre).strip()
    if not slug_base:
        raise HTTPException(status_code=400, detail="slug_base inválido")

    tenant = TenantService.create_tenant(
        session,
        nombre=payload.nombre,
        slug_base=slug_base,
        creado_por=admin_user.id,
        activo=payload.activo,
    )
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    tenant.suscripcion_plan = "mensual"
    tenant.suscripcion_estado = "activa" if payload.activo else "suspendida"
    tenant.suscripcion_hasta = now + timedelta(days=settings.subscription_default_days)
    tenant.suscripcion_gracia_hasta = tenant.suscripcion_hasta + timedelta(days=settings.subscription_grace_days)
    tenant.suscripcion_ultima_cobranza = now
    session.add(tenant)
    session.commit()
    TenantService.add_user_to_tenant(session, tenant_id=tenant.id, user_id=owner.id, rol=payload.owner_rol)

    return TenantRead(id=tenant.id, id_ext=str(tenant.id_ext), nombre=tenant.nombre, slug=tenant.slug)


@router.post("/admin/{tenant_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def admin_add_member(
    tenant_id: int,
    payload: AdminTenantMembershipRequest,
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    tenant_row = session.get(Tenant, tenant_id)
    if tenant_row is None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    user = UserService.get_user_by_email(session, payload.user_email)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    TenantService.add_user_to_tenant(session, tenant_id=tenant_id, user_id=user.id, rol=payload.rol)
    return None
