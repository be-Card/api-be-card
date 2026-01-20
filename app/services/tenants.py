from __future__ import annotations

import re
from typing import List, Optional

from sqlmodel import Session, select

from app.models.tenant import Tenant, TenantUser
from app.models.sales_point import PuntoVenta


def _slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-")[:80] or "tenant"


class TenantService:
    @staticmethod
    def get_tenant_by_slug(session: Session, slug: str) -> Optional[Tenant]:
        return session.exec(select(Tenant).where(Tenant.slug == slug)).first()

    @staticmethod
    def get_tenants_for_user(session: Session, user_id: int) -> List[Tenant]:
        stmt = (
            select(Tenant)
            .join(TenantUser, TenantUser.tenant_id == Tenant.id)
            .where(TenantUser.user_id == user_id)
            .where(Tenant.activo == True)
            .order_by(Tenant.nombre, Tenant.id)
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def user_in_tenant(session: Session, user_id: int, tenant_id: int) -> bool:
        stmt = (
            select(TenantUser)
            .where(TenantUser.user_id == user_id)
            .where(TenantUser.tenant_id == tenant_id)
        )
        return session.exec(stmt).first() is not None

    @staticmethod
    def create_tenant_for_user(
        session: Session,
        *,
        nombre: str,
        slug_base: str,
        user_id: int,
        rol: str = "owner",
    ) -> Tenant:
        tenant = TenantService.create_tenant(
            session,
            nombre=nombre,
            slug_base=slug_base,
            creado_por=user_id,
        )
        TenantService.add_user_to_tenant(session, tenant_id=tenant.id, user_id=user_id, rol=rol)
        return tenant

    @staticmethod
    def create_tenant(
        session: Session,
        *,
        nombre: str,
        slug_base: str,
        creado_por: Optional[int],
        activo: bool = True,
    ) -> Tenant:
        base = _slugify(slug_base)
        slug = base
        existing_slugs = set(
            session.exec(select(Tenant.slug).where(Tenant.slug.like(f"{base}%"))).all()
        )
        if slug in existing_slugs:
            suffix = 2
            while f"{base}-{suffix}" in existing_slugs:
                suffix += 1
            slug = f"{base}-{suffix}"

        tenant = Tenant(nombre=nombre, slug=slug, creado_por=creado_por, activo=activo)
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

        pv = session.exec(select(PuntoVenta).where(PuntoVenta.tenant_id == tenant.id).limit(1)).first()
        if pv is None:
            pv = PuntoVenta(
                nombre="Principal",
                calle="Sin calle",
                altura=1,
                localidad="Sin localidad",
                provincia="Sin provincia",
                tenant_id=tenant.id,
                activo=True,
                creado_por=creado_por,
                id_usuario_socio=creado_por,
            )
            session.add(pv)
            session.commit()
        return tenant

    @staticmethod
    def add_user_to_tenant(
        session: Session,
        *,
        tenant_id: int,
        user_id: int,
        rol: str = "member",
    ) -> TenantUser:
        existing = session.exec(
            select(TenantUser)
            .where(TenantUser.tenant_id == tenant_id)
            .where(TenantUser.user_id == user_id)
        ).first()
        if existing is not None:
            if rol and existing.rol != rol:
                existing.rol = rol
                session.add(existing)
                session.commit()
                session.refresh(existing)
            return existing

        membership = TenantUser(tenant_id=tenant_id, user_id=user_id, rol=rol)
        session.add(membership)
        session.commit()
        session.refresh(membership)
        return membership

    @staticmethod
    def sweep_expired_subscriptions(session: Session) -> int:
        from datetime import datetime

        now = datetime.utcnow()
        stmt = (
            select(Tenant)
            .where(Tenant.activo == True)
            .where(Tenant.suscripcion_hasta.is_not(None))
            .where(Tenant.suscripcion_hasta < now)
            .where(
                (Tenant.suscripcion_gracia_hasta.is_(None)) | (Tenant.suscripcion_gracia_hasta < now)
            )
        )
        tenants = list(session.exec(stmt).all())
        for t in tenants:
            t.activo = False
            t.suscripcion_estado = "suspendida"
            session.add(t)
        if tenants:
            session.commit()
        return len(tenants)
