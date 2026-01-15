"""
Router para endpoints de pricing (reglas y cálculo)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, SQLModel
from typing import List, Optional

from ..core.database import get_session
from ..core.tenant import get_current_tenant
from .auth import get_current_active_user
from ..models.tenant import Tenant
from ..models.user_extended import Usuario
from ..models.pricing import (
    ReglaDePrecioCreate,
    ReglaDePrecioRead,
    ReglaDePrecioUpdate,
    ConsultaPrecio,
    CalculoPrecio,
)
from ..services.pricing import PricingService


router = APIRouter(prefix="/pricing", tags=["pricing"])
logger = logging.getLogger(__name__)


class ReglaListResponse(SQLModel):
    reglas: List[ReglaDePrecioRead]
    total: int
    page: int
    per_page: int


@router.get("/reglas", response_model=ReglaListResponse)
def list_reglas(
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(10, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar por nombre"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    estado: Optional[str] = Query(None, description="Filtrar por estado calculado (Activa, Programada, Inactiva)"),
    order_dir: str = Query("asc", description="Orden por nombre (asc/desc)"),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    skip = (page - 1) * per_page
    try:
        reglas, total = PricingService.list_reglas(
            session,
            tenant_id=tenant.id,
            skip=skip,
            limit=per_page,
            search=search,
            activo=activo,
            estado=estado,
            order_dir=order_dir,
        )
    except ValueError as e:
        logger.warning("Error listando reglas", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail="Parámetros inválidos")
    return ReglaListResponse(reglas=reglas, total=total, page=page, per_page=per_page)


@router.post("/reglas", response_model=ReglaDePrecioRead, status_code=status.HTTP_201_CREATED)
def create_regla(
    data: ReglaDePrecioCreate,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
):
    try:
        regla = PricingService.create_regla(session, data, tenant_id=tenant.id, user_id=current_user.id)
        return regla
    except Exception as e:
        logger.exception("Error creando regla", extra={"user_id": current_user.id})
        raise HTTPException(status_code=400, detail="No se pudo crear la regla")


@router.get("/reglas/{regla_id}", response_model=ReglaDePrecioRead)
def get_regla(
    regla_id: int,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
):
    regla = PricingService.get_regla(session, regla_id, tenant_id=tenant.id)
    if not regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return regla


@router.patch("/reglas/{regla_id}", response_model=ReglaDePrecioRead)
def update_regla(
    regla_id: int,
    data: ReglaDePrecioUpdate,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
):
    regla = PricingService.update_regla(session, regla_id, data, tenant_id=tenant.id)
    if not regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return regla


@router.delete("/reglas/{regla_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_regla(
    regla_id: int,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
):
    ok = PricingService.delete_regla(session, regla_id, tenant_id=tenant.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Regla no encontrada")


@router.post("/calcular", response_model=CalculoPrecio)
def calcular_precio(
    consulta: ConsultaPrecio,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
):
    try:
        calculo = PricingService.calcular_precio(session, consulta, tenant_id=tenant.id)
        return calculo
    except ValueError as e:
        logger.warning("Precio no encontrado", extra={"error": str(e)})
        raise HTTPException(status_code=404, detail="No se encontró un precio aplicable")
    except Exception as e:
        logger.exception("Error calculando precio")
        raise HTTPException(status_code=400, detail="No se pudo calcular el precio")
