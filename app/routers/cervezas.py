"""
Router para endpoints de cervezas
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, SQLModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from ..core.database import get_session
from .auth import get_current_user
from ..models.user_extended import Usuario
from ..models.beer import (
    CervezaCreate, CervezaRead, CervezaUpdate,
    TipoEstiloCervezaRead, PrecioCervezaCreate, PrecioCervezaRead
)
from ..services.cervezas import CervezaService


router = APIRouter(prefix="/cervezas", tags=["cervezas"])


class CervezaResponse(SQLModel):
    """Respuesta para lista de cervezas con paginación"""
    cervezas: List[CervezaRead]
    total: int
    page: int
    per_page: int
    size: int
    total_pages: int


class CervezaCreateRequest(CervezaCreate):
    """Request para crear cerveza con precio inicial"""
    precio_inicial: Optional[Decimal] = None


class CervezaUpdateRequest(CervezaUpdate):
    """Request para actualizar cerveza con nuevo precio"""
    precio_nuevo: Optional[Decimal] = None
    motivo_precio: Optional[str] = None


# Endpoints de soporte (deben ir antes de las rutas con parámetros dinámicos)

@router.get("/estilos", response_model=List[TipoEstiloCervezaRead])
def get_estilos_cerveza(session: Session = Depends(get_session)):
    """Obtener todos los estilos de cerveza"""
    return CervezaService.get_estilos_cerveza(session)


@router.get("/", response_model=CervezaResponse)
def get_cervezas(
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(10, ge=1, le=100, description="Elementos por página"),
    size: Optional[int] = Query(None, ge=1, le=100, description="Alias de per_page (compatibilidad)"),
    search: Optional[str] = Query(None, description="Buscar por nombre, tipo o proveedor"),
    estilo_id: Optional[int] = Query(None, description="Filtrar por ID de estilo"),
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    destacado: Optional[bool] = Query(None, description="Filtrar por destacado"),
    order_dir: str = Query("asc", description="Dirección de orden (asc/desc)"),
    session: Session = Depends(get_session)
):
    """Obtener lista de cervezas con filtros y paginación"""
    
    effective_size = size if size is not None else per_page
    skip = (page - 1) * effective_size
    
    cervezas, total = CervezaService.get_cervezas_with_filters(
        session=session,
        skip=skip,
        limit=effective_size,
        search=search,
        estilo_id=estilo_id,
        activo=activo,
        destacado=destacado,
        order_dir=order_dir,
    )
    
    # Las cervezas ya vienen con precio_actual y stock_total desde _cerveza_to_read
    return CervezaResponse(
        cervezas=cervezas,
        total=total,
        page=page,
        per_page=effective_size,
        size=effective_size,
        total_pages=(total + effective_size - 1) // effective_size if effective_size > 0 else 1,
    )


@router.get("/{cerveza_id}", response_model=CervezaRead)
def get_cerveza(
    cerveza_id: int,
    session: Session = Depends(get_session)
):
    """Obtener cerveza por ID"""
    
    cerveza = CervezaService.get_cerveza_by_id(session, cerveza_id)
    if not cerveza:
        raise HTTPException(status_code=404, detail="Cerveza no encontrada")
    
    # Agregar datos adicionales
    cerveza_dict = cerveza.model_dump()
    cerveza_dict["precio_actual"] = CervezaService.get_precio_actual(session, cerveza_id)
    cerveza_dict["stock_total"] = CervezaService.calculate_stock_total(session, cerveza_id)
    
    return cerveza_dict


@router.post("/", response_model=CervezaRead, status_code=201)
def create_cerveza(
    cerveza_data: CervezaCreateRequest,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user)
):
    """Crear nueva cerveza"""
    
    try:
        # Extraer precio inicial del request
        precio_inicial = cerveza_data.precio_inicial
        cerveza_create = CervezaCreate(**cerveza_data.model_dump(exclude={'precio_inicial'}))
        
        cerveza = CervezaService.create_cerveza(
            session=session,
            cerveza_data=cerveza_create,
            user_id=current_user.id,
            precio_inicial=precio_inicial
        )
        
        # Agregar datos adicionales
        cerveza_dict = cerveza.model_dump()
        cerveza_dict["precio_actual"] = CervezaService.get_precio_actual(session, cerveza.id)
        cerveza_dict["stock_total"] = CervezaService.calculate_stock_total(session, cerveza.id)
        
        return cerveza_dict
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{cerveza_id}", response_model=CervezaRead)
def update_cerveza(
    cerveza_id: int,
    cerveza_data: CervezaUpdateRequest,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user)
):
    """Actualizar cerveza"""
    
    try:
        # Extraer datos de precio del request
        precio_nuevo = cerveza_data.precio_nuevo
        motivo_precio = cerveza_data.motivo_precio
        cerveza_update = CervezaUpdate(
            **cerveza_data.model_dump(exclude_unset=True, exclude={'precio_nuevo', 'motivo_precio'})
        )
        
        cerveza = CervezaService.update_cerveza(
            session=session,
            cerveza_id=cerveza_id,
            cerveza_data=cerveza_update,
            user_id=current_user.id,
            precio_nuevo=precio_nuevo,
            motivo_precio=motivo_precio
        )
        
        if not cerveza:
            raise HTTPException(status_code=404, detail="Cerveza no encontrada")
        
        # Agregar datos adicionales
        cerveza_dict = cerveza.model_dump()
        cerveza_dict["precio_actual"] = CervezaService.get_precio_actual(session, cerveza_id)
        cerveza_dict["stock_total"] = CervezaService.calculate_stock_total(session, cerveza_id)
        
        return cerveza_dict
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.delete("/{cerveza_id}", status_code=204)
def delete_cerveza(
    cerveza_id: int,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user)
):
    """Eliminar cerveza (soft delete)"""
    
    success = CervezaService.delete_cerveza(session, cerveza_id)
    if not success:
        raise HTTPException(status_code=404, detail="Cerveza no encontrada")


@router.get("/{cerveza_id}/precio-actual", response_model=dict)
def get_precio_actual(
    cerveza_id: int,
    session: Session = Depends(get_session)
):
    """Obtener precio actual de una cerveza"""
    
    precio = CervezaService.get_precio_actual(session, cerveza_id)
    if precio is None:
        raise HTTPException(status_code=404, detail="Precio no encontrado")
    
    return {"precio": precio}


@router.get("/{cerveza_id}/stock", response_model=dict)
def get_stock_cerveza(
    cerveza_id: int,
    session: Session = Depends(get_session)
):
    """Obtener stock total de una cerveza"""
    
    stock = CervezaService.calculate_stock_total(session, cerveza_id)
    return {"stock_total": stock}


@router.post("/{cerveza_id}/precios", response_model=PrecioCervezaRead, status_code=201)
def create_precio_cerveza(
    cerveza_id: int,
    precio_data: PrecioCervezaCreate,
    session: Session = Depends(get_session),
    current_user: Usuario = Depends(get_current_user)
):
    """Crear nuevo precio para una cerveza"""
    
    # Verificar que la cerveza existe
    cerveza = CervezaService.get_cerveza_by_id(session, cerveza_id)
    if not cerveza:
        raise HTTPException(status_code=404, detail="Cerveza no encontrada")
    
    # Actualizar con nuevo precio
    cerveza_update = CervezaUpdate()
    updated_cerveza = CervezaService.update_cerveza(
        session=session,
        cerveza_id=cerveza_id,
        cerveza_data=cerveza_update,
        user_id=current_user.id,
        precio_nuevo=precio_data.precio,
        motivo_precio=precio_data.motivo
    )
    
    # Obtener el precio recién creado
    precio_actual = CervezaService.get_precio_actual(session, cerveza_id)
    
    return {
        "id": 0,  # Se podría mejorar obteniendo el ID real del precio
        "id_cerveza": cerveza_id,
        "precio": precio_actual,
        "fecha_inicio": datetime.utcnow(),
        "fecha_fin": None,
        "creado_por": current_user.id,
        "motivo": precio_data.motivo
    }
