"""
Router para operaciones de clientes
Endpoints optimizados basados en el análisis del schema SQL
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.tenant import get_current_tenant
from app.models.tenant import Tenant
from app.routers.auth import get_current_active_user
from app.services.clients import ClientService
from app.models.user_extended import Usuario
from app.schemas.clients import (
    ClientListResponse, ClientDetailResponse, ClientUpdateRequest,
    ClientStatusToggleRequest, ClientStatusToggleResponse,
    ClientCreateRequest,
    LoyaltyHistoryResponse,
    ClientRewardsResponse,
)

router = APIRouter(prefix="/clients", tags=["clients"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=ClientListResponse)
async def get_clients(
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(20, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar por nombre o email"),
    status: Optional[str] = Query(None, description="Filtrar por estado (Activo/Inactivo)"),
    loyalty_level: Optional[str] = Query(None, description="Filtrar por nivel de lealtad"),
    sort_by: str = Query("name", description="Campo para ordenar (name, joinDate, totalSpent, loyaltyPoints)"),
    sort_order: str = Query("asc", description="Orden (asc/desc)"),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """
    Obtener lista paginada de clientes con filtros y ordenamiento
    
    - **page**: Número de página (por defecto 1)
    - **limit**: Elementos por página (por defecto 20, máximo 100)
    - **search**: Buscar por nombre o email
    - **status**: Filtrar por estado (Activo/Inactivo)
    - **loyalty_level**: Filtrar por nivel de lealtad
    - **sort_by**: Campo para ordenar (name, joinDate, totalSpent, loyaltyPoints)
    - **sort_order**: Orden ascendente (asc) o descendente (desc)
    """
    result = ClientService.get_clients_paginated(
        session=session,
        tenant_id=tenant.id,
        page=page,
        limit=limit,
        search=search,
        status=status,
        loyalty_level=loyalty_level,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return ClientListResponse(
        clients=result["clients"],
        pagination=result["pagination"],
        filters=result["filters"],
    )


@router.post("/", response_model=ClientDetailResponse, status_code=201)
async def create_client(
    payload: ClientCreateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    result = ClientService.create_client(
        session,
        tenant_id=tenant.id,
        creado_por=current_user.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
        gender=payload.gender,
        birth_date=payload.birthDate,
    )

    return ClientDetailResponse(
        client=result["client"],
        stats=result["stats"],
        loyalty=result["loyalty"],
        recentOrders=result["recent_orders"],
        paymentMethods=result["payment_methods"],
    )


@router.get("/{client_id}", response_model=ClientDetailResponse)
async def get_client_detail(
    client_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """
    Obtener detalle completo de un cliente específico
    
    - **client_id**: ID externo del cliente
    """
    result = ClientService.get_client_detail(session, client_id, tenant_id=tenant.id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    return ClientDetailResponse(
        client=result["client"],
        stats=result["stats"],
        loyalty=result["loyalty"],
        recentOrders=result["recent_orders"],
        paymentMethods=result["payment_methods"],
    )


@router.put("/{client_id}", response_model=ClientDetailResponse)
async def update_client(
    client_id: str,
    update_data: ClientUpdateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """
    Actualizar información de un cliente
    
    - **client_id**: ID externo del cliente
    - **update_data**: Datos a actualizar
    """
    update_dict = update_data.model_dump(exclude_none=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No se proporcionaron datos para actualizar")

    result = ClientService.update_client(session, client_id, update_dict, tenant_id=tenant.id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    return ClientDetailResponse(
        client=result["client"],
        stats=result["stats"],
        loyalty=result["loyalty"],
        recentOrders=result["recent_orders"],
        paymentMethods=result["payment_methods"],
    )


@router.patch("/{client_id}/status", response_model=ClientStatusToggleResponse)
async def toggle_client_status(
    client_id: str,
    status_data: ClientStatusToggleRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """
    Alternar estado activo/inactivo de un cliente
    
    - **client_id**: ID externo del cliente
    - **status_data**: Datos del cambio de estado (incluye razón opcional)
    """
    result = ClientService.toggle_client_status(session, client_id, tenant_id=tenant.id, reason=status_data.reason)
    if not result:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    return ClientStatusToggleResponse(
        client=result["client"],
        previousStatus=result["previous_status"],
        newStatus=result["new_status"],
        message=f"Estado del cliente cambiado de {result['previous_status']} a {result['new_status']}",
    )


@router.get("/{client_id}/stats")
async def get_client_stats(
    client_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """
    Obtener estadísticas específicas de un cliente
    
    - **client_id**: ID externo del cliente
    """
    result = ClientService.get_client_detail(session, client_id, tenant_id=tenant.id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    return {"stats": result["stats"], "loyalty": result["loyalty"]}


@router.get("/{client_id}/orders")
async def get_client_orders(
    client_id: str,
    limit: int = Query(20, ge=1, le=100, description="Número de órdenes a obtener"),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """
    Obtener órdenes de un cliente específico
    
    - **client_id**: ID externo del cliente
    - **limit**: Número máximo de órdenes a retornar
    """
    client_detail = ClientService.get_client_detail(session, client_id, tenant_id=tenant.id)
    if not client_detail:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    return {"orders": client_detail["recent_orders"][:limit]}


@router.get("/{client_id}/loyalty/history")
async def get_client_loyalty_history(
    client_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """
    Obtener historial de puntos de lealtad de un cliente
    
    - **client_id**: ID externo del cliente
    """
    client_detail = ClientService.get_client_detail(session, client_id, tenant_id=tenant.id)
    if not client_detail:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    user_id = session.exec(select(Usuario.id).where(Usuario.id_ext == client_id, Usuario.tenant_id == tenant.id)).first()
    if not user_id:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    transactions = ClientService.get_loyalty_history(session, int(user_id), limit=100)
    return LoyaltyHistoryResponse(transactions=transactions, summary=client_detail["loyalty"])


@router.get("/{client_id}/payment-methods")
async def get_client_payment_methods(
    client_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """
    Obtener métodos de pago de un cliente
    
    - **client_id**: ID externo del cliente
    """
    client_detail = ClientService.get_client_detail(session, client_id, tenant_id=tenant.id)
    if not client_detail:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    return {"paymentMethods": client_detail["payment_methods"]}


@router.get("/{client_id}/rewards", response_model=ClientRewardsResponse)
async def get_client_rewards(
    client_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    client_detail = ClientService.get_client_detail(session, client_id, tenant_id=tenant.id)
    if not client_detail:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    user = session.exec(select(Usuario).where(Usuario.id_ext == client_id, Usuario.tenant_id == tenant.id)).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Cliente con ID {client_id} no encontrado")

    data = ClientService.get_rewards(session, user.id)
    return ClientRewardsResponse(**data)


@router.post("/{client_id}/rewards/{premio_id}/redeem")
async def redeem_client_reward(
    client_id: str,
    premio_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    try:
        return ClientService.redeem_reward(session, client_id, premio_id, tenant_id=tenant.id)
    except ValueError as e:
        logger.warning("Error canjeando premio", extra={"client_id": client_id, "premio_id": premio_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="No se pudo canjear el premio")
