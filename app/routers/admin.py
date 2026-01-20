from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlmodel import Session, SQLModel, select, func

from app.core.database import get_session
from app.core.config import settings
from app.models.tenant import Tenant, TenantPayment, TenantUser
from app.models.user_extended import TipoRolUsuario, Usuario, UsuarioRol
from app.routers.auth import require_admin
from app.services.tenants import TenantService


router = APIRouter(prefix="/admin", tags=["admin"])


class AdminTenantBrief(SQLModel):
    id: int
    nombre: str
    slug: str
    activo: bool
    rol: str


class AdminUserRow(SQLModel):
    id: int
    id_ext: str
    nombre_usuario: Optional[str] = None
    email: str
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    activo: bool
    verificado: bool
    roles: List[str]
    tenants: List[AdminTenantBrief]


class AdminUsersResponse(SQLModel):
    users: List[AdminUserRow]
    total: int
    skip: int
    limit: int


class AdminSetActiveRequest(SQLModel):
    activo: bool


class AdminSetSubscriptionRequest(SQLModel):
    suscripcion_plan: Optional[str] = None
    suscripcion_estado: Optional[str] = None
    suscripcion_hasta: Optional[datetime] = None
    suscripcion_gracia_hasta: Optional[datetime] = None
    suscripcion_ultima_cobranza: Optional[datetime] = None
    suscripcion_precio_centavos: Optional[int] = None
    suscripcion_moneda: Optional[str] = None
    suscripcion_periodo_dias: Optional[int] = None


class AdminRenewSubscriptionRequest(SQLModel):
    months: int = 1
    amount_centavos: Optional[int] = None
    currency: Optional[str] = None
    paid_at: Optional[datetime] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    failure_reason: Optional[str] = None
    provider: Optional[str] = None
    provider_payment_id: Optional[str] = None


class AdminCreatePaymentRequest(SQLModel):
    amount_centavos: int
    currency: str = "ARS"
    paid_at: Optional[datetime] = None
    status: str = "paid"
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    failure_reason: Optional[str] = None
    provider: Optional[str] = None
    provider_payment_id: Optional[str] = None
    months: int = 1


class AdminUpdatePaymentRequest(SQLModel):
    status: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    failure_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None


class AdminTenantPaymentRow(SQLModel):
    id: int
    id_ext: str
    amount_centavos: int
    currency: str
    status: str
    paid_at: datetime
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    failure_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    provider: Optional[str] = None
    provider_payment_id: Optional[str] = None


class AdminTenantPaymentsResponse(SQLModel):
    payments: List[AdminTenantPaymentRow]


class AdminTenantRow(SQLModel):
    id: int
    id_ext: str
    nombre: str
    slug: str
    activo: bool
    suscripcion_plan: str
    suscripcion_estado: str
    suscripcion_hasta: Optional[datetime] = None
    suscripcion_gracia_hasta: Optional[datetime] = None
    suscripcion_precio_centavos: int
    suscripcion_moneda: str
    suscripcion_periodo_dias: int
    dias_restantes: Optional[int] = None
    en_gracia: bool = False
    members_count: int
    owner_emails: List[str]


class AdminTenantsResponse(SQLModel):
    tenants: List[AdminTenantRow]
    total: int
    skip: int
    limit: int


@router.get("/users", response_model=AdminUsersResponse)
def admin_list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    search: Optional[str] = Query(default=None),
    activo: Optional[bool] = Query(default=None),
    verificado: Optional[bool] = Query(default=None),
    pending_activation: Optional[bool] = Query(default=None),
    has_tenant: Optional[bool] = Query(default=None),
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    filters = [Usuario.email.is_not(None)]
    if pending_activation is True:
        filters.append(Usuario.activo == False)
        filters.append(Usuario.verificado == True)
    else:
        if activo is not None:
            filters.append(Usuario.activo == activo)
        if verificado is not None:
            filters.append(Usuario.verificado == verificado)

    if search:
        search_norm = search.strip().lower()
        if search_norm:
            pattern = f"%{search_norm}%"
            filters.append(
                or_(
                    func.lower(Usuario.email).like(pattern),
                    func.lower(Usuario.nombre_usuario).like(pattern),
                    func.lower(Usuario.nombres).like(pattern),
                    func.lower(Usuario.apellidos).like(pattern),
                )
            )

    stmt = select(Usuario).where(*filters).order_by(Usuario.id.desc()).offset(skip).limit(limit)
    users = list(session.exec(stmt).all())
    user_ids = [u.id for u in users if u.id is not None]

    total_stmt = select(func.count()).select_from(Usuario).where(*filters)
    total = int(session.exec(total_stmt).one())

    roles_by_user: Dict[int, List[str]] = {uid: [] for uid in user_ids}
    if user_ids:
        role_rows = session.exec(
            select(UsuarioRol.id_usuario, TipoRolUsuario.tipo)
            .join(TipoRolUsuario, TipoRolUsuario.id == UsuarioRol.id_rol)
            .where(UsuarioRol.id_usuario.in_(user_ids))
            .where(UsuarioRol.fecha_revocacion.is_(None))
        ).all()
        for uid, role_tipo in role_rows:
            if uid is not None:
                roles_by_user.setdefault(uid, []).append(role_tipo)

    tenants_by_user: Dict[int, List[AdminTenantBrief]] = {uid: [] for uid in user_ids}
    if user_ids:
        tenant_rows = session.exec(
            select(
                TenantUser.user_id,
                Tenant.id,
                Tenant.nombre,
                Tenant.slug,
                Tenant.activo,
                TenantUser.rol,
            )
            .join(Tenant, Tenant.id == TenantUser.tenant_id)
            .where(TenantUser.user_id.in_(user_ids))
            .order_by(Tenant.nombre, Tenant.id)
        ).all()
        for user_id, tenant_id, nombre, slug, tenant_activo, rol in tenant_rows:
            if user_id is None or tenant_id is None:
                continue
            tenants_by_user.setdefault(user_id, []).append(
                AdminTenantBrief(
                    id=int(tenant_id),
                    nombre=str(nombre),
                    slug=str(slug),
                    activo=bool(tenant_activo),
                    rol=str(rol),
                )
            )

    rows = [
        AdminUserRow(
            id=u.id,
            id_ext=str(u.id_ext),
            nombre_usuario=u.nombre_usuario,
            email=u.email,
            nombres=u.nombres,
            apellidos=u.apellidos,
            activo=u.activo,
            verificado=u.verificado,
            roles=sorted(set(roles_by_user.get(u.id, []))),
            tenants=tenants_by_user.get(u.id, []),
        )
        for u in users
        if u.id is not None
    ]

    if has_tenant is True:
        rows = [r for r in rows if len(r.tenants) > 0]
    elif has_tenant is False:
        rows = [r for r in rows if len(r.tenants) == 0]

    return AdminUsersResponse(users=rows, total=total, skip=skip, limit=limit)


@router.patch("/users/{user_id}/active", status_code=status.HTTP_204_NO_CONTENT)
def admin_set_user_active(
    user_id: int,
    payload: AdminSetActiveRequest,
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    user = session.get(Usuario, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.activo = payload.activo
    session.add(user)
    session.commit()
    return None


@router.get("/tenants", response_model=AdminTenantsResponse)
def admin_list_tenants(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    search: Optional[str] = Query(default=None),
    activo: Optional[bool] = Query(default=None),
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    filters = []
    if activo is not None:
        filters.append(Tenant.activo == activo)

    if search:
        search_norm = search.strip().lower()
        if search_norm:
            pattern = f"%{search_norm}%"
            filters.append(
                or_(
                    func.lower(Tenant.nombre).like(pattern),
                    func.lower(Tenant.slug).like(pattern),
                )
            )

    stmt = select(Tenant).where(*filters).order_by(Tenant.nombre, Tenant.id).offset(skip).limit(limit)
    tenants = list(session.exec(stmt).all())
    tenant_ids = [t.id for t in tenants if t.id is not None]

    total_stmt = select(func.count()).select_from(Tenant).where(*filters)
    total = int(session.exec(total_stmt).one())

    members_count: Dict[int, int] = {tid: 0 for tid in tenant_ids}
    owner_emails: Dict[int, List[str]] = {tid: [] for tid in tenant_ids}

    if tenant_ids:
        count_rows = session.exec(
            select(TenantUser.tenant_id, func.count())
            .where(TenantUser.tenant_id.in_(tenant_ids))
            .group_by(TenantUser.tenant_id)
        ).all()
        for tenant_id, count in count_rows:
            if tenant_id is not None:
                members_count[int(tenant_id)] = int(count)

        owner_rows = session.exec(
            select(TenantUser.tenant_id, Usuario.email)
            .join(Usuario, Usuario.id == TenantUser.user_id)
            .where(TenantUser.tenant_id.in_(tenant_ids))
            .where(TenantUser.rol == "owner")
        ).all()
        for tenant_id, email in owner_rows:
            if tenant_id is not None and email:
                owner_emails.setdefault(int(tenant_id), []).append(email)

    now = datetime.utcnow()
    rows = []
    for t in tenants:
        if t.id is None:
            continue
        dias_restantes = None
        en_gracia = False
        if t.suscripcion_hasta is not None:
            dias_restantes = int((t.suscripcion_hasta - now).total_seconds() // 86400)
            if dias_restantes < 0 and t.suscripcion_gracia_hasta is not None:
                en_gracia = now <= t.suscripcion_gracia_hasta

        rows.append(
            AdminTenantRow(
                id=t.id,
                id_ext=str(t.id_ext),
                nombre=t.nombre,
                slug=t.slug,
                activo=t.activo,
                suscripcion_plan=t.suscripcion_plan,
                suscripcion_estado=t.suscripcion_estado,
                suscripcion_hasta=t.suscripcion_hasta,
                suscripcion_gracia_hasta=t.suscripcion_gracia_hasta,
                suscripcion_precio_centavos=t.suscripcion_precio_centavos,
                suscripcion_moneda=t.suscripcion_moneda,
                suscripcion_periodo_dias=t.suscripcion_periodo_dias,
                dias_restantes=dias_restantes,
                en_gracia=en_gracia,
                members_count=members_count.get(t.id, 0),
                owner_emails=sorted(set(owner_emails.get(t.id, []))),
            )
        )

    return AdminTenantsResponse(tenants=rows, total=total, skip=skip, limit=limit)


@router.patch("/tenants/{tenant_id}/active", status_code=status.HTTP_204_NO_CONTENT)
def admin_set_tenant_active(
    tenant_id: int,
    payload: AdminSetActiveRequest,
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    tenant.activo = payload.activo
    session.add(tenant)
    session.commit()
    return None


@router.patch("/tenants/{tenant_id}/subscription", status_code=status.HTTP_204_NO_CONTENT)
def admin_set_tenant_subscription(
    tenant_id: int,
    payload: AdminSetSubscriptionRequest,
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    if payload.suscripcion_plan is not None:
        tenant.suscripcion_plan = payload.suscripcion_plan.strip() or tenant.suscripcion_plan
    if payload.suscripcion_estado is not None:
        tenant.suscripcion_estado = payload.suscripcion_estado.strip() or tenant.suscripcion_estado
    if payload.suscripcion_hasta is not None:
        tenant.suscripcion_hasta = payload.suscripcion_hasta
    if payload.suscripcion_gracia_hasta is not None:
        tenant.suscripcion_gracia_hasta = payload.suscripcion_gracia_hasta
    if payload.suscripcion_ultima_cobranza is not None:
        tenant.suscripcion_ultima_cobranza = payload.suscripcion_ultima_cobranza
    if payload.suscripcion_precio_centavos is not None:
        tenant.suscripcion_precio_centavos = int(payload.suscripcion_precio_centavos)
    if payload.suscripcion_moneda is not None:
        tenant.suscripcion_moneda = payload.suscripcion_moneda.strip().upper() or tenant.suscripcion_moneda
    if payload.suscripcion_periodo_dias is not None:
        tenant.suscripcion_periodo_dias = int(payload.suscripcion_periodo_dias)

    session.add(tenant)
    session.commit()
    return None


@router.post("/tenants/{tenant_id}/subscription/renew", status_code=status.HTTP_204_NO_CONTENT)
def admin_renew_tenant_subscription(
    tenant_id: int,
    payload: AdminRenewSubscriptionRequest,
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    months = payload.months if payload.months and payload.months > 0 else 1
    paid_at = payload.paid_at or datetime.utcnow()
    base = tenant.suscripcion_hasta if tenant.suscripcion_hasta and tenant.suscripcion_hasta > paid_at else paid_at
    period_days = tenant.suscripcion_periodo_dias if tenant.suscripcion_periodo_dias and tenant.suscripcion_periodo_dias > 0 else 30
    period_start = base
    period_end = base + timedelta(days=period_days * months)

    amount_centavos = (
        payload.amount_centavos
        if payload.amount_centavos is not None
        else int(tenant.suscripcion_precio_centavos or 0) * months
    )
    currency = (payload.currency or tenant.suscripcion_moneda or "ARS").strip().upper()
    status_value = (payload.status or "paid").strip().lower()

    payment = TenantPayment(
        tenant_id=tenant.id,
        amount_centavos=int(amount_centavos),
        currency=currency,
        status=status_value,
        paid_at=paid_at,
        payment_method=payload.payment_method,
        notes=payload.notes,
        failure_reason=payload.failure_reason,
        period_start=period_start,
        period_end=period_end,
        provider=payload.provider,
        provider_payment_id=payload.provider_payment_id,
        creado_por=_admin_user.id,
    )
    session.add(payment)

    if status_value == "paid":
        tenant.suscripcion_hasta = period_end
        tenant.suscripcion_gracia_hasta = tenant.suscripcion_hasta + timedelta(days=settings.subscription_grace_days)
        tenant.suscripcion_estado = "activa"
        tenant.suscripcion_ultima_cobranza = paid_at
        tenant.activo = True
        session.add(tenant)

    session.commit()
    return None


@router.post("/subscriptions/sweep", response_model=dict)
def admin_sweep_expired_subscriptions(
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    count = TenantService.sweep_expired_subscriptions(session)
    return {"disabled_tenants": count}


@router.get("/tenants/{tenant_id}/payments", response_model=AdminTenantPaymentsResponse)
def admin_list_tenant_payments(
    tenant_id: int,
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    rows = list(
        session.exec(
            select(TenantPayment)
            .where(TenantPayment.tenant_id == tenant_id)
            .order_by(TenantPayment.paid_at.desc(), TenantPayment.id.desc())
            .limit(200)
        ).all()
    )
    return AdminTenantPaymentsResponse(
        payments=[
            AdminTenantPaymentRow(
                id=p.id,
                id_ext=str(p.id_ext),
                amount_centavos=p.amount_centavos,
                currency=p.currency,
                status=p.status,
                paid_at=p.paid_at,
                payment_method=p.payment_method,
                notes=p.notes,
                failure_reason=p.failure_reason,
                refunded_at=p.refunded_at,
                period_start=p.period_start,
                period_end=p.period_end,
                provider=p.provider,
                provider_payment_id=p.provider_payment_id,
            )
            for p in rows
            if p.id is not None
        ]
    )


@router.post("/tenants/{tenant_id}/payments", status_code=status.HTTP_201_CREATED)
def admin_create_tenant_payment(
    tenant_id: int,
    payload: AdminCreatePaymentRequest,
    session: Session = Depends(get_session),
    admin_user: Usuario = Depends(require_admin),
):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    months = payload.months if payload.months and payload.months > 0 else 1
    paid_at = payload.paid_at or datetime.utcnow()
    base = tenant.suscripcion_hasta if tenant.suscripcion_hasta and tenant.suscripcion_hasta > paid_at else paid_at
    period_days = tenant.suscripcion_periodo_dias if tenant.suscripcion_periodo_dias and tenant.suscripcion_periodo_dias > 0 else 30
    period_start = base
    period_end = base + timedelta(days=period_days * months)

    status_value = (payload.status or "paid").strip().lower()
    payment = TenantPayment(
        tenant_id=tenant.id,
        amount_centavos=int(payload.amount_centavos),
        currency=(payload.currency or "ARS").strip().upper(),
        status=status_value,
        paid_at=paid_at,
        payment_method=payload.payment_method,
        notes=payload.notes,
        failure_reason=payload.failure_reason,
        period_start=period_start,
        period_end=period_end,
        provider=payload.provider,
        provider_payment_id=payload.provider_payment_id,
        creado_por=admin_user.id,
    )
    session.add(payment)

    if status_value == "paid":
        tenant.suscripcion_hasta = period_end
        tenant.suscripcion_gracia_hasta = tenant.suscripcion_hasta + timedelta(days=settings.subscription_grace_days)
        tenant.suscripcion_estado = "activa"
        tenant.suscripcion_ultima_cobranza = paid_at
        tenant.activo = True
        session.add(tenant)
    session.commit()
    session.refresh(payment)
    return {"payment_id": payment.id, "period_end": tenant.suscripcion_hasta.isoformat() if tenant.suscripcion_hasta else None}


@router.patch("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_update_payment(
    payment_id: int,
    payload: AdminUpdatePaymentRequest,
    session: Session = Depends(get_session),
    _admin_user: Usuario = Depends(require_admin),
):
    payment = session.get(TenantPayment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    if payload.status is not None:
        payment.status = payload.status.strip().lower() or payment.status
    if payload.payment_method is not None:
        payment.payment_method = payload.payment_method.strip() or payload.payment_method
    if payload.notes is not None:
        payment.notes = payload.notes
    if payload.failure_reason is not None:
        payment.failure_reason = payload.failure_reason
    if payload.refunded_at is not None:
        payment.refunded_at = payload.refunded_at

    session.add(payment)
    session.commit()
    return None
