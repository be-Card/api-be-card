"""
Router para reportes y análisis
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select
from typing import Annotated, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_session
from app.routers.auth import require_admin_or_socio
from app.models.user_extended import Usuario
from app.models.beer import Cerveza
from app.models.sales import Venta

router = APIRouter(prefix="/reports", tags=["reports"])


# Schemas para reportes
class VentaDiaria(BaseModel):
    """Detalle de ventas por día"""
    fecha: str
    ingresos: float
    litros_vendidos: float
    transacciones: int
    ticket_promedio: float


class VentasReportResponse(BaseModel):
    """Respuesta del reporte de ventas"""
    periodo_inicio: str
    periodo_fin: str
    datos: List[VentaDiaria]
    total_ingresos: float
    total_litros: float
    total_transacciones: int


class ConsumoEstilo(BaseModel):
    """Consumo por estilo de cerveza"""
    estilo: str
    litros: float
    porcentaje: float
    color: str = "#f06f26"  # Color por defecto


class ConsumoReportResponse(BaseModel):
    """Respuesta del reporte de consumo"""
    periodo_inicio: str
    periodo_fin: str
    datos: List[ConsumoEstilo]
    total_litros: float


class ClienteNivel(BaseModel):
    """Estadísticas por nivel de cliente"""
    nivel: str
    cantidad: int
    gasto_promedio: float
    gasto_total: float


class ClientesReportResponse(BaseModel):
    """Respuesta del reporte de clientes"""
    periodo_inicio: str
    periodo_fin: str
    datos: List[ClienteNivel]
    total_clientes: int


# Colores por estilo de cerveza
COLORES_ESTILOS = {
    "IPA": "#F0682D",
    "Lager": "#299D58",
    "Stout": "#F5970A",
    "Ale": "#0DA2E7",
    "Porter": "#8B4513",
    "Pilsen": "#f8d02d",
    "Wheat": "#FFD700",
    "Amber": "#FF8C00"
}

def _parse_ymd(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")

def _resolve_period(days: int, date_from: Optional[str], date_to: Optional[str]) -> tuple[datetime, datetime]:
    if date_from and date_to:
        start = _parse_ymd(date_from)
        end = _parse_ymd(date_to) + timedelta(days=1) - timedelta(microseconds=1)
        if start > end:
            raise HTTPException(status_code=400, detail="Rango de fechas inválido")
        if (end - start).days > 365:
            raise HTTPException(status_code=400, detail="El rango máximo es de 365 días")
        return start, end
    fecha_fin = datetime.now()
    fecha_inicio = fecha_fin - timedelta(days=days)
    return fecha_inicio, fecha_fin


@router.get("/ventas", response_model=VentasReportResponse)
def get_reporte_ventas(
    current_user: Annotated[Usuario, Depends(require_admin_or_socio)],
    session: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=365, description="Número de días del reporte"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    """
    Obtener reporte de ventas diarias

    Incluye:
    - Ingresos por día
    - Litros vendidos
    - Número de transacciones
    - Ticket promedio

    **Parámetros:**
    - days: Número de días hacia atrás (default: 30)
    """
    fecha_inicio, fecha_fin = _resolve_period(days, date_from, date_to)

    # Obtener ventas del período
    statement = select(Venta).where(
        Venta.fecha_hora >= fecha_inicio,
        Venta.fecha_hora <= fecha_fin
    ).order_by(Venta.fecha_hora)

    ventas = session.exec(statement).all()

    # Agrupar por fecha
    ventas_por_dia = {}
    for venta in ventas:
        fecha_str = venta.fecha_hora.strftime('%Y-%m-%d')

        if fecha_str not in ventas_por_dia:
            ventas_por_dia[fecha_str] = {
                'ingresos': 0.0,
                'litros': 0.0,
                'transacciones': 0
            }

        ventas_por_dia[fecha_str]['ingresos'] += float(venta.monto_total)
        ventas_por_dia[fecha_str]['transacciones'] += 1

        # Calcular litros vendidos desde la venta directamente
        if venta.id_cerveza is not None:
            ventas_por_dia[fecha_str]['litros'] += venta.cantidad_ml / 1000.0

    # Crear lista de datos diarios
    datos_diarios = []
    total_ingresos = 0.0
    total_litros = 0.0
    total_transacciones = 0

    for fecha_str in sorted(ventas_por_dia.keys()):
        dia_data = ventas_por_dia[fecha_str]
        ticket_promedio = dia_data['ingresos'] / dia_data['transacciones'] if dia_data['transacciones'] > 0 else 0

        datos_diarios.append(VentaDiaria(
            fecha=fecha_str,
            ingresos=dia_data['ingresos'],
            litros_vendidos=dia_data['litros'],
            transacciones=dia_data['transacciones'],
            ticket_promedio=ticket_promedio
        ))

        total_ingresos += dia_data['ingresos']
        total_litros += dia_data['litros']
        total_transacciones += dia_data['transacciones']

    return VentasReportResponse(
        periodo_inicio=fecha_inicio.strftime('%Y-%m-%d'),
        periodo_fin=fecha_fin.strftime('%Y-%m-%d'),
        datos=datos_diarios,
        total_ingresos=total_ingresos,
        total_litros=total_litros,
        total_transacciones=total_transacciones
    )


@router.get("/consumo", response_model=ConsumoReportResponse)
def get_reporte_consumo(
    current_user: Annotated[Usuario, Depends(require_admin_or_socio)],
    session: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=365, description="Número de días del reporte"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    """
    Obtener reporte de consumo por estilo de cerveza

    Muestra la distribución de litros vendidos por estilo de cerveza

    **Parámetros:**
    - days: Número de días hacia atrás (default: 30)
    """
    fecha_inicio, fecha_fin = _resolve_period(days, date_from, date_to)

    # Obtener ventas del período con sus detalles
    statement = select(Venta).where(
        Venta.fecha_hora >= fecha_inicio,
        Venta.fecha_hora <= fecha_fin
    )

    ventas = session.exec(statement).all()

    # Agrupar por estilo de cerveza
    consumo_por_estilo = {}
    total_litros = 0.0

    for venta in ventas:
        # Usar la información directa de la venta
        if venta.id_cerveza is not None:
            cerveza = session.get(Cerveza, venta.id_cerveza)
            if cerveza:
                estilo = cerveza.tipo or "Otro"
                litros = venta.cantidad_ml / 1000.0

                if estilo not in consumo_por_estilo:
                    consumo_por_estilo[estilo] = 0.0

                consumo_por_estilo[estilo] += litros
                total_litros += litros

    # Calcular porcentajes y crear lista de datos
    datos_consumo = []
    for estilo in sorted(consumo_por_estilo.keys(), key=lambda x: consumo_por_estilo[x], reverse=True):
        litros = consumo_por_estilo[estilo]
        porcentaje = (litros / total_litros * 100) if total_litros > 0 else 0
        color = COLORES_ESTILOS.get(estilo, "#f06f26")

        datos_consumo.append(ConsumoEstilo(
            estilo=estilo,
            litros=round(litros, 2),
            porcentaje=round(porcentaje, 1),
            color=color
        ))

    return ConsumoReportResponse(
        periodo_inicio=fecha_inicio.strftime('%Y-%m-%d'),
        periodo_fin=fecha_fin.strftime('%Y-%m-%d'),
        datos=datos_consumo,
        total_litros=round(total_litros, 2)
    )


@router.get("/clientes", response_model=ClientesReportResponse)
def get_reporte_clientes(
    current_user: Annotated[Usuario, Depends(require_admin_or_socio)],
    session: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=365, description="Número de días del reporte"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    """
    Obtener reporte de segmentación de clientes

    Muestra estadísticas por nivel de fidelización (Oro, Plata, Bronce)

    Criterios de clasificación:
    - Oro: 10+ compras
    - Plata: 5-9 compras
    - Bronce: 1-4 compras

    **Parámetros:**
    - days: Número de días hacia atrás (default: 30)
    """
    fecha_inicio, fecha_fin = _resolve_period(days, date_from, date_to)

    # Obtener todas las ventas del período
    statement = select(Venta).where(
        Venta.fecha_hora >= fecha_inicio,
        Venta.fecha_hora <= fecha_fin
    )

    ventas = session.exec(statement).all()

    # Agrupar por cliente
    clientes_data = {}
    for venta in ventas:
        cliente_id = venta.id_usuario

        if cliente_id not in clientes_data:
            clientes_data[cliente_id] = {
                'num_compras': 0,
                'total_gastado': 0.0
            }

        clientes_data[cliente_id]['num_compras'] += 1
        clientes_data[cliente_id]['total_gastado'] += float(venta.monto_total)

    # Clasificar clientes por nivel
    niveles = {
        'Oro': {'cantidad': 0, 'gasto_total': 0.0, 'clientes': []},
        'Plata': {'cantidad': 0, 'gasto_total': 0.0, 'clientes': []},
        'Bronce': {'cantidad': 0, 'gasto_total': 0.0, 'clientes': []}
    }

    for cliente_id, data in clientes_data.items():
        num_compras = data['num_compras']
        gasto = data['total_gastado']

        if num_compras >= 10:
            nivel = 'Oro'
        elif num_compras >= 5:
            nivel = 'Plata'
        else:
            nivel = 'Bronce'

        niveles[nivel]['cantidad'] += 1
        niveles[nivel]['gasto_total'] += gasto
        niveles[nivel]['clientes'].append(gasto)

    # Crear lista de datos por nivel
    datos_niveles = []
    total_clientes = 0

    for nivel in ['Oro', 'Plata', 'Bronce']:
        nivel_data = niveles[nivel]
        cantidad = nivel_data['cantidad']
        gasto_total = nivel_data['gasto_total']
        gasto_promedio = gasto_total / cantidad if cantidad > 0 else 0

        datos_niveles.append(ClienteNivel(
            nivel=nivel,
            cantidad=cantidad,
            gasto_promedio=round(gasto_promedio, 2),
            gasto_total=round(gasto_total, 2)
        ))

        total_clientes += cantidad

    return ClientesReportResponse(
        periodo_inicio=fecha_inicio.strftime('%Y-%m-%d'),
        periodo_fin=fecha_fin.strftime('%Y-%m-%d'),
        datos=datos_niveles,
        total_clientes=total_clientes
    )
