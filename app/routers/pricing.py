"""
Router para endpoints de pricing (reglas y cálculo)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, SQLModel
from typing import List, Optional
from datetime import datetime

from ..core.database import get_session
from .auth import get_current_user, require_admin, require_admin_or_socio
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
    session: Session = Depends(get_session),
):
    skip = (page - 1) * per_page
    try:
        reglas, total = PricingService.list_reglas(
            session,
            skip=skip,
            limit=per_page,
            search=search,
            activo=activo,
            estado=estado,
            order_dir=order_dir,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ReglaListResponse(reglas=reglas, total=total, page=page, per_page=per_page)


@router.post("/reglas", response_model=ReglaDePrecioRead, status_code=status.HTTP_201_CREATED)
def create_regla(
    data: ReglaDePrecioCreate,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin_or_socio),
):
    try:
        regla = PricingService.create_regla(session, data, user_id=current_user.id)
        return regla
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reglas/{regla_id}", response_model=ReglaDePrecioRead)
def get_regla(
    regla_id: int,
    session: Session = Depends(get_session),
):
    regla = PricingService.get_regla(session, regla_id)
    if not regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return regla


@router.patch("/reglas/{regla_id}", response_model=ReglaDePrecioRead)
def update_regla(
    regla_id: int,
    data: ReglaDePrecioUpdate,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin_or_socio),
):
    regla = PricingService.update_regla(session, regla_id, data)
    if not regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return regla


@router.delete("/reglas/{regla_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_regla(
    regla_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(require_admin_or_socio),
):
    ok = PricingService.delete_regla(session, regla_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Regla no encontrada")


@router.post("/calcular", response_model=CalculoPrecio)
def calcular_precio(
    consulta: ConsultaPrecio,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user),
):
    try:
        calculo = PricingService.calcular_precio(session, consulta)
        return calculo
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
