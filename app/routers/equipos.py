"""
Router para endpoints de equipos
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, SQLModel, select
from typing import List, Optional
import logging
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from ..core.database import get_session
from ..core.tenant import get_current_tenant
from .auth import get_current_user
from ..models.tenant import Tenant
from ..models.user_extended import Usuario

logger = logging.getLogger(__name__)
from ..models.sales_point import (
    Equipo, EquipoCreate, EquipoRead, EquipoUpdate,
    TipoEstadoEquipoRead, TipoBarrilRead, PuntoVentaRead, PuntoVenta
)
from ..services.equipos import (
    EquipoService, EquipoDetailRead, CambiarCervezaRequest
)
from ..services.alertas import AlertaService


router = APIRouter(prefix="/equipos", tags=["equipos"])


def _equipo_belongs_to_tenant(session: Session, *, equipo_id: int, tenant_id: int) -> bool:
    stmt = (
        select(Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(Equipo.id == equipo_id, PuntoVenta.tenant_id == tenant_id)
    )
    return session.exec(stmt).first() is not None


class EquipoResponse(SQLModel):
    """Respuesta para lista de equipos"""
    equipos: List[EquipoDetailRead]
    total: int
    page: int
    size: int
    total_pages: int


class CambiarEstadoRequest(SQLModel):
    """Request para cambiar estado de equipo"""
    id_estado_equipo: int
    motivo: Optional[str] = None


class ActualizarTemperaturaRequest(SQLModel):
    """Request para actualizar temperatura"""
    temperatura: float


class PuntoVentaListRead(SQLModel):
    id: int
    id_ext: str
    nombre: str
    codigo_punto_venta: Optional[str] = None


class SimularConsumoRequest(SQLModel):
    """Request para simular consumo de barril"""
    litros_consumidos: float


# Endpoints de soporte (deben ir antes de las rutas con parámetros dinámicos)

@router.get("/tipos-barril", response_model=List[TipoBarrilRead])
def get_tipos_barril(session: Session = Depends(get_session)):
    """Obtener todos los tipos de barril"""
    return EquipoService.get_tipos_barril(session)


@router.get("/estados-equipo", response_model=List[TipoEstadoEquipoRead])
def get_estados_equipo(session: Session = Depends(get_session)):
    """Obtener todos los estados de equipo"""
    return EquipoService.get_estados_equipo(session)


@router.get("/puntos-venta", response_model=List[PuntoVentaListRead])
def get_puntos_venta(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    puntos = session.exec(
        select(PuntoVenta)
        .where(PuntoVenta.tenant_id == tenant.id)
        .order_by(PuntoVenta.nombre)
    ).all()
    return [PuntoVentaListRead(id=p.id, id_ext=str(p.id_ext), nombre=p.nombre, codigo_punto_venta=p.codigo_punto_venta) for p in puntos]


@router.get("/stock-bajo", response_model=EquipoResponse)
def get_equipos_stock_bajo(
    umbral: int = Query(20, ge=1, le=100, description="Umbral de porcentaje para stock bajo"),
    session: Session = Depends(get_session)
):
    """Obtener equipos con stock bajo"""
    
    equipos = EquipoService.get_equipos_con_stock_bajo(session, umbral)
    
    return EquipoResponse(equipos=equipos)


@router.get("/alertas")
def get_alertas_activas(session: Session = Depends(get_session)):
    """Obtener alertas activas de stock"""
    return AlertaService.get_alertas_activas(session)


@router.get("/alertas/verificar")
def verificar_alertas_stock(session: Session = Depends(get_session)):
    """Verificar y obtener todas las alertas de stock"""
    alertas = AlertaService.verificar_alertas_stock(session)
    return {
        "alertas": [alerta.to_dict() for alerta in alertas],
        "total": len(alertas)
    }


@router.get("/alertas/atencion")
def get_equipos_requieren_atencion(session: Session = Depends(get_session)):
    """Obtener equipos que requieren atención inmediata"""
    equipos = EquipoService.get_equipos_con_stock_bajo(session, 20)
    return {
        "total": len(equipos),
        "mensaje": "Equipos que requieren atención inmediata (stock ≤ 20%)",
        "equipos": equipos,
    }


@router.get("/", response_model=EquipoResponse)
def get_equipos(
    page: int = Query(1, ge=1, description="Número de página"),
    size: int = Query(10, ge=1, le=100, description="Tamaño de página"),
    search: Optional[str] = Query(None, description="Buscar por nombre de equipo"),
    permite_ventas: Optional[bool] = Query(None, description="Filtrar por estado (En Línea/Fuera de Línea)"),
    order_dir: str = Query("asc", description="Dirección de orden (asc/desc)"),
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    """Obtener lista de equipos con detalles completos"""
    
    equipos = EquipoService.get_equipos_with_details(session, tenant_id=tenant.id)

    if search:
        search_lower = search.strip().lower()
        equipos = [
            e for e in equipos
            if (getattr(e, "nombre_equipo", None) or "").lower().find(search_lower) >= 0
        ]

    if permite_ventas is not None:
        equipos = [
            e for e in equipos
            if bool(getattr(getattr(e, "estado", None), "permite_ventas", False)) == bool(permite_ventas)
        ]

    if order_dir.lower() == "desc":
        equipos = sorted(equipos, key=lambda e: (getattr(e, "nombre_equipo", "") or "", getattr(e, "id", 0)), reverse=True)
    else:
        equipos = sorted(equipos, key=lambda e: (getattr(e, "nombre_equipo", "") or "", getattr(e, "id", 0)))

    total = len(equipos)
    total_pages = (total + size - 1) // size if size > 0 else 1
    
    # Aplicar paginación
    start_index = (page - 1) * size
    end_index = start_index + size
    equipos_paginados = equipos[start_index:end_index]
    
    return EquipoResponse(equipos=equipos_paginados, total=total, page=page, size=size, total_pages=total_pages)


@router.get("/{equipo_id}", response_model=EquipoDetailRead)
def get_equipo(
    equipo_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session)
):
    """Obtener equipo por ID"""
    if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    
    equipo = EquipoService.get_equipo_by_id(session, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    
    return equipo


@router.get("/by-id-ext/{equipo_id_ext}", response_model=EquipoDetailRead)
def get_equipo_by_id_ext(
    equipo_id_ext: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    equipo = EquipoService.get_equipo_by_id_ext(session, tenant_id=tenant.id, equipo_id_ext=equipo_id_ext)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


@router.get("/by-code/{codigo_equipo}", response_model=EquipoDetailRead)
def get_equipo_by_codigo(
    codigo_equipo: str,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    equipo = EquipoService.get_equipo_by_codigo(session, tenant_id=tenant.id, codigo_equipo=codigo_equipo)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


@router.post("/", response_model=EquipoDetailRead, status_code=201)
def create_equipo(
    equipo_data: EquipoCreate,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user)
):
    """Crear nuevo equipo"""
    
    try:
        if equipo_data.id_punto_de_venta is not None:
            pv = session.exec(
                select(PuntoVenta.id).where(PuntoVenta.id == equipo_data.id_punto_de_venta, PuntoVenta.tenant_id == tenant.id)
            ).first()
            if pv is None:
                raise ValueError("Punto de venta inválido")
        equipo = EquipoService.create_equipo(
            session=session,
            equipo_data=equipo_data,
            user_id=current_user.id,
            tenant_id=tenant.id,
        )
        
        return equipo
    except ValueError as e:
        logger.warning("Error validando equipo", extra={"error": str(e), "user_id": current_user.id})
        raise HTTPException(status_code=400, detail="Datos inválidos")
    except Exception:
        logger.exception("Error creando equipo", extra={"user_id": current_user.id})
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/{equipo_id}/simular-consumo")
def simular_consumo_barril(
    equipo_id: int,
    request: SimularConsumoRequest,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session)
):
    """Simular consumo de barril y verificar alertas"""
    
    try:
        if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        resultado = AlertaService.simular_consumo_barril(
            session=session,
            equipo_id=equipo_id,
            litros_consumidos=request.litros_consumidos
        )
        
        return resultado
    except ValueError as e:
        logger.warning("Error simulando consumo", extra={"equipo_id": equipo_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="Datos inválidos")
    except Exception:
        logger.exception("Error simulando consumo", extra={"equipo_id": equipo_id})
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.put("/{equipo_id}", response_model=EquipoDetailRead)
def update_equipo(
    equipo_id: int,
    equipo_data: EquipoUpdate,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user)
):
    """Actualizar equipo"""
    
    try:
        if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        equipo = EquipoService.update_equipo(
            session=session,
            equipo_id=equipo_id,
            equipo_data=equipo_data,
            user_id=current_user.id
        )
        
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        
        return equipo
    except ValueError as e:
        logger.warning("Error validando actualización de equipo", extra={"equipo_id": equipo_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="Datos inválidos")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error actualizando equipo", extra={"equipo_id": equipo_id, "user_id": current_user.id})
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.put("/{equipo_id}/cambiar-cerveza", response_model=EquipoDetailRead)
def cambiar_cerveza_equipo(
    equipo_id: int,
    request: CambiarCervezaRequest,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user)
):
    """Cambiar cerveza de un equipo"""

    logger.debug(
        f"Changing beer for equipment {equipo_id}, "
        f"new beer: {request.id_cerveza}, user: {current_user.id}"
    )

    try:
        if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        equipo = EquipoService.cambiar_cerveza_equipo(
            session=session,
            equipo_id=equipo_id,
            nueva_cerveza_id=request.id_cerveza,
            capacidad_nueva=request.capacidad_nueva,
            id_barril=request.id_barril,
            user_id=current_user.id,
            motivo=request.motivo
        )

        if not equipo:
            logger.warning(f"Equipment not found: {equipo_id}")
            raise HTTPException(status_code=404, detail="Equipo no encontrado")

        logger.info(f"Successfully changed beer for equipment {equipo_id}")
        return equipo

    except ValueError as e:
        logger.warning("Error validando cambio de cerveza", extra={"equipo_id": equipo_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="Datos inválidos")
    except Exception:
        logger.exception(f"Error changing beer for equipment {equipo_id}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.put("/{equipo_id}/estado", response_model=EquipoDetailRead)
def cambiar_estado_equipo(
    equipo_id: int,
    request: CambiarEstadoRequest,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user)
):
    """Cambiar estado de un equipo"""
    
    try:
        if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        equipo = EquipoService.toggle_estado_equipo(
            session=session,
            equipo_id=equipo_id,
            nuevo_estado_id=request.id_estado_equipo,
            user_id=current_user.id,
            motivo=request.motivo
        )
        
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        
        return equipo
        
    except ValueError as e:
        logger.warning("Error validando cambio de estado", extra={"equipo_id": equipo_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="Datos inválidos")
    except Exception:
        logger.exception("Error cambiando estado", extra={"equipo_id": equipo_id, "user_id": current_user.id})
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.put("/{equipo_id}/toggle-estado", response_model=EquipoDetailRead)
def toggle_estado_equipo(
    equipo_id: int,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user)
):
    """Alternar estado del equipo entre Activo e Inactivo"""
    
    try:
        if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        equipo = EquipoService.toggle_estado_simple(
            session=session,
            equipo_id=equipo_id,
            user_id=current_user.id
        )
        
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        
        return equipo
        
    except ValueError as e:
        logger.warning("Error validando toggle de estado", extra={"equipo_id": equipo_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="Datos inválidos")
    except Exception:
        logger.exception("Error toggleando estado", extra={"equipo_id": equipo_id, "user_id": current_user.id})
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.put("/{equipo_id}/temperatura", response_model=EquipoDetailRead)
def actualizar_temperatura(
    equipo_id: int,
    request: ActualizarTemperaturaRequest,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session)
):
    """Actualizar temperatura del equipo"""
    
    try:
        if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        equipo = EquipoService.update_temperatura(
            session=session,
            equipo_id=equipo_id,
            temperatura=request.temperatura
        )
        
        if not equipo:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        
        return equipo
        
    except ValueError as e:
        logger.warning("Error validando temperatura", extra={"equipo_id": equipo_id, "error": str(e)})
        raise HTTPException(status_code=400, detail="Datos inválidos")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error actualizando temperatura", extra={"equipo_id": equipo_id})
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.delete("/{equipo_id}", status_code=204)
def delete_equipo(
    equipo_id: int,
    session: Session = Depends(get_session),
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_user)
):
    if not _equipo_belongs_to_tenant(session, equipo_id=equipo_id, tenant_id=tenant.id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    equipo = session.get(Equipo, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    try:
        session.delete(equipo)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar el equipo porque tiene datos asociados"
        )
