from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlmodel import Session

from app.core.database import get_session
from app.models.tenant import Tenant
from app.models.user_extended import Usuario
from app.routers.auth import get_current_active_user
from app.services.tenants import TenantService


def _tenant_slug_from_host(host: str) -> Optional[str]:
    host_no_port = host.split(":", 1)[0].strip().lower()
    if not host_no_port:
        return None

    parts = host_no_port.split(".")
    if len(parts) < 4:
        return None

    base = ".".join(parts[-3:])
    if base != "becard.com.ar":
        return None

    subdomain = parts[-4]
    if subdomain == "clientes":
        return None

    return subdomain


def get_tenant_slug(
    request: Request,
    x_tenant_slug: Optional[str] = Header(default=None, alias="X-Tenant-Slug"),
) -> Optional[str]:
    if x_tenant_slug:
        return x_tenant_slug.strip().lower()
    return _tenant_slug_from_host(request.headers.get("host", ""))


def get_current_tenant(
    tenant_slug: Optional[str] = Depends(get_tenant_slug),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> Tenant:
    tenants = TenantService.get_tenants_for_user(session, current_user.id)

    if not tenant_slug:
        if len(tenants) == 1:
            return tenants[0]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant requerido",
        )

    tenant = TenantService.get_tenant_by_slug(session, tenant_slug)
    if tenant is None or not tenant.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")

    now = datetime.utcnow()
    if tenant.suscripcion_hasta is not None and now > tenant.suscripcion_hasta:
        if tenant.suscripcion_gracia_hasta is None or now > tenant.suscripcion_gracia_hasta:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Suscripción vencida")

    if not TenantService.user_in_tenant(session, current_user.id, tenant.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al tenant")

    return tenant
