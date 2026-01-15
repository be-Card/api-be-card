"""
Router para dashboard - KPIs y estadísticas generales
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from typing import Annotated
from decimal import Decimal

from app.core.database import get_session
from app.core.tenant import get_current_tenant
from app.routers.auth import get_current_active_user
from app.models.tenant import Tenant
from app.models.user_extended import Usuario
from app.models.sales import Venta
from app.models.beer import Cerveza
from app.models.sales_point import Equipo, TipoBarril, TipoEstadoEquipo, PuntoVenta
from app.models.transactions import Pago, TipoEstadoPago
from app.models.user_extended import TipoMetodoPago

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis")
def get_dashboard_kpis(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
    days: int = 30
):
    """
    Obtener KPIs principales del dashboard

    Requiere usuario autenticado con acceso al tenant
    """
    # Calcular fecha de inicio según días solicitados
    fecha_inicio = datetime.utcnow() - timedelta(days=days)

    # Total de ventas en el período
    total_ventas_statement = (
        select(func.sum(Venta.monto_total))
        .join(Equipo, Venta.id_equipo == Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(Venta.fecha_hora >= fecha_inicio)
        .where(PuntoVenta.tenant_id == tenant.id)
    )
    total_ventas = session.exec(total_ventas_statement).first() or Decimal('0')

    # Número de transacciones en el período
    num_transacciones_statement = (
        select(func.count(Venta.id))
        .join(Equipo, Venta.id_equipo == Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(Venta.fecha_hora >= fecha_inicio)
        .where(PuntoVenta.tenant_id == tenant.id)
    )
    num_transacciones = session.exec(num_transacciones_statement).first() or 0

    # Total de clientes activos
    clientes_activos_statement = select(func.count(Usuario.id)).where(
        Usuario.activo == True,
        Usuario.tenant_id == tenant.id,
    )
    clientes_activos = session.exec(clientes_activos_statement).first() or 0

    # Total de cervezas activas
    cervezas_activas_statement = select(func.count(Cerveza.id)).where(
        Cerveza.activo == True,
        Cerveza.tenant_id == tenant.id,
    )
    cervezas_activas = session.exec(cervezas_activas_statement).first() or 0

    # Equipos activos
    equipos_activos_statement = (
        select(func.count(Equipo.id))
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(PuntoVenta.tenant_id == tenant.id)
        .where(Equipo.id_estado_equipo.in_([1, 2]))
    )
    equipos_activos = session.exec(equipos_activos_statement).first() or 0

    # Ticket promedio
    ticket_promedio = (
        float(total_ventas) / num_transacciones
        if num_transacciones > 0
        else 0
    )

    # Ventas del período anterior para calcular % de cambio
    fecha_inicio_anterior = fecha_inicio - timedelta(days=days)
    total_ventas_anterior_statement = select(func.sum(Venta.monto_total)).where(
        Venta.fecha_hora >= fecha_inicio_anterior,
        Venta.fecha_hora < fecha_inicio
    )
    total_ventas_anterior_statement = (
        total_ventas_anterior_statement
        .join(Equipo, Venta.id_equipo == Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(PuntoVenta.tenant_id == tenant.id)
    )
    total_ventas_anterior = session.exec(total_ventas_anterior_statement).first() or Decimal('0')

    # Calcular cambio porcentual
    if float(total_ventas_anterior) > 0:
        cambio_ventas = ((float(total_ventas) - float(total_ventas_anterior)) / float(total_ventas_anterior)) * 100
    else:
        cambio_ventas = 100.0 if float(total_ventas) > 0 else 0.0

    return {
        "periodo_dias": days,
        "total_ventas": float(total_ventas),
        "num_transacciones": num_transacciones,
        "ticket_promedio": round(ticket_promedio, 2),
        "clientes_activos": clientes_activos,
        "cervezas_activas": cervezas_activas,
        "equipos_activos": equipos_activos,
        "cambio_ventas_porcentaje": round(cambio_ventas, 2)
    }


@router.get("/ventas-por-dia")
def get_ventas_por_dia(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
    days: int = 30
):
    """
    Obtener ventas agrupadas por día para gráficos

    Requiere usuario autenticado con acceso al tenant
    """
    fecha_inicio = datetime.utcnow() - timedelta(days=days)

    # Agrupar ventas por día
    from sqlalchemy import cast, Date
    ventas_statement = select(
        cast(Venta.fecha_hora, Date).label("fecha"),
        func.sum(Venta.monto_total).label("total"),
        func.count(Venta.id).label("cantidad")
    ).join(
        Equipo, Venta.id_equipo == Equipo.id
    ).join(
        PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id
    ).where(
        Venta.fecha_hora >= fecha_inicio,
        PuntoVenta.tenant_id == tenant.id,
    ).group_by("fecha").order_by("fecha")

    result = session.exec(ventas_statement).all()

    return {
        "periodo_dias": days,
        "datos": [
            {
                "fecha": str(row[0]),
                "total": float(row[1]) if row[1] else 0,
                "cantidad": row[2]
            }
            for row in result
        ]
    }


@router.get("/cervezas-populares")
def get_cervezas_populares(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
    days: int = 30,
    limit: int = 10
):
    """
    Obtener las cervezas más vendidas en el período

    Requiere usuario autenticado con acceso al tenant
    """
    fecha_inicio = datetime.utcnow() - timedelta(days=days)

    # Top cervezas por ventas
    cervezas_statement = select(
        Cerveza.nombre,
        Cerveza.tipo,
        func.sum(Venta.cantidad_ml).label("total_ml"),
        func.sum(Venta.monto_total).label("total_ventas"),
        func.count(Venta.id).label("num_ventas")
    ).join(
        Venta, Venta.id_cerveza == Cerveza.id
    ).join(
        Equipo, Venta.id_equipo == Equipo.id
    ).join(
        PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id
    ).where(
        Venta.fecha_hora >= fecha_inicio,
        PuntoVenta.tenant_id == tenant.id,
        Cerveza.tenant_id == tenant.id,
    ).group_by(
        Cerveza.id, Cerveza.nombre, Cerveza.tipo
    ).order_by(
        func.sum(Venta.monto_total).desc()
    ).limit(limit)

    result = session.exec(cervezas_statement).all()

    return {
        "periodo_dias": days,
        "cervezas": [
            {
                "nombre": row[0],
                "tipo": row[1],
                "total_ml": row[2],
                "total_ventas": float(row[3]) if row[3] else 0,
                "num_ventas": row[4]
            }
            for row in result
        ]
    }


@router.get("/clientes-top")
def get_top_clientes(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
    days: int = 30,
    limit: int = 10
):
    """
    Obtener los clientes con mayor consumo en el período

    Requiere usuario autenticado con acceso al tenant
    """
    fecha_inicio = datetime.utcnow() - timedelta(days=days)

    # Top clientes por gasto
    clientes_statement = select(
        Usuario.nombres,
        Usuario.apellidos,
        Usuario.email,
        Usuario.codigo_cliente,
        func.sum(Venta.monto_total).label("total_gastado"),
        func.count(Venta.id).label("num_compras")
    ).join(
        Venta, Venta.id_usuario == Usuario.id
    ).join(
        Equipo, Venta.id_equipo == Equipo.id
    ).join(
        PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id
    ).where(
        Venta.fecha_hora >= fecha_inicio,
        PuntoVenta.tenant_id == tenant.id,
    ).group_by(
        Usuario.id, Usuario.nombres, Usuario.apellidos, Usuario.email, Usuario.codigo_cliente
    ).order_by(
        func.sum(Venta.monto_total).desc()
    ).limit(limit)

    result = session.exec(clientes_statement).all()

    return {
        "periodo_dias": days,
        "clientes": [
            {
                "nombre_completo": f"{row[0]} {row[1]}",
                "email": row[2],
                "codigo_cliente": row[3],
                "total_gastado": float(row[4]) if row[4] else 0,
                "num_compras": row[5],
                "nivel": "Oro" if row[5] >= 10 else "Plata" if row[5] >= 5 else "Bronce",
            }
            for row in result
        ]
    }


@router.get("/resumen-equipos")
def get_resumen_equipos(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session)
):
    """
    Obtener resumen del estado de los equipos

    Requiere usuario autenticado con acceso al tenant
    """
    # Contar equipos por estado
    from app.models.sales_point import TipoEstadoEquipo

    equipos_statement = select(
        TipoEstadoEquipo.estado,
        func.count(Equipo.id).label("cantidad")
    ).join(
        Equipo, Equipo.id_estado_equipo == TipoEstadoEquipo.id
    ).join(
        PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id
    ).where(
        PuntoVenta.tenant_id == tenant.id
    ).group_by(
        TipoEstadoEquipo.id, TipoEstadoEquipo.estado
    )

    result = session.exec(equipos_statement).all()

    # Total de equipos
    total_equipos = sum(row[1] for row in result)

    return {
        "total_equipos": total_equipos,
        "por_estado": [
            {
                "estado": row[0],
                "cantidad": row[1]
            }
            for row in result
        ]
    }


@router.get("/kpis-dia")
def get_dashboard_kpis_dia(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    now = datetime.utcnow()
    hoy_inicio = datetime(now.year, now.month, now.day)
    hoy_fin = hoy_inicio + timedelta(days=1)
    ayer_inicio = hoy_inicio - timedelta(days=1)
    ayer_fin = hoy_inicio

    def _sum_monto(start: datetime, end: datetime) -> float:
        stmt = (
            select(func.sum(Venta.monto_total))
            .join(Equipo, Venta.id_equipo == Equipo.id)
            .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
            .where(Venta.fecha_hora >= start, Venta.fecha_hora < end)
            .where(PuntoVenta.tenant_id == tenant.id)
        )
        value = session.exec(stmt).first() or Decimal("0")
        return float(value)

    def _count_transacciones(start: datetime, end: datetime) -> int:
        stmt = (
            select(func.count(Venta.id))
            .join(Equipo, Venta.id_equipo == Equipo.id)
            .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
            .where(Venta.fecha_hora >= start, Venta.fecha_hora < end)
            .where(PuntoVenta.tenant_id == tenant.id)
        )
        return session.exec(stmt).first() or 0

    def _sum_litros(start: datetime, end: datetime) -> float:
        stmt = (
            select(func.sum(Venta.cantidad_ml))
            .join(Equipo, Venta.id_equipo == Equipo.id)
            .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
            .where(Venta.fecha_hora >= start, Venta.fecha_hora < end)
            .where(PuntoVenta.tenant_id == tenant.id)
        )
        value = session.exec(stmt).first() or 0
        return float(value) / 1000.0

    def _count_clientes_unicos(start: datetime, end: datetime) -> int:
        stmt = (
            select(func.count(func.distinct(Venta.id_usuario)))
            .join(Equipo, Venta.id_equipo == Equipo.id)
            .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
            .where(
                Venta.fecha_hora >= start,
                Venta.fecha_hora < end,
                Venta.id_usuario != None,
                PuntoVenta.tenant_id == tenant.id,
            )
        )
        return session.exec(stmt).first() or 0

    ingresos_hoy = _sum_monto(hoy_inicio, hoy_fin)
    ingresos_ayer = _sum_monto(ayer_inicio, ayer_fin)
    litros_hoy = _sum_litros(hoy_inicio, hoy_fin)
    litros_ayer = _sum_litros(ayer_inicio, ayer_fin)
    clientes_hoy = _count_clientes_unicos(hoy_inicio, hoy_fin)
    clientes_ayer = _count_clientes_unicos(ayer_inicio, ayer_fin)
    transacciones_hoy = _count_transacciones(hoy_inicio, hoy_fin)
    transacciones_ayer = _count_transacciones(ayer_inicio, ayer_fin)

    consumo_promedio = ingresos_hoy / transacciones_hoy if transacciones_hoy > 0 else 0.0
    consumo_ayer = ingresos_ayer / transacciones_ayer if transacciones_ayer > 0 else 0.0

    def _pct_change(current: float, previous: float) -> float:
        if previous > 0:
            return ((current - previous) / previous) * 100.0
        return 100.0 if current > 0 else 0.0

    return {
        "ingresos_dia": round(ingresos_hoy, 2),
        "ingresos_cambio_pct": round(_pct_change(ingresos_hoy, ingresos_ayer), 1),
        "litros_servidos": round(litros_hoy, 0),
        "litros_cambio_pct": round(_pct_change(litros_hoy, litros_ayer), 1),
        "clientes_unicos": clientes_hoy,
        "clientes_cambio_pct": round(_pct_change(float(clientes_hoy), float(clientes_ayer)), 1),
        "consumo_promedio": round(consumo_promedio, 0),
        "consumo_cambio_pct": round(_pct_change(consumo_promedio, consumo_ayer), 1),
    }


@router.get("/distribucion-estilo")
def get_distribucion_por_estilo(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
    days: int = 30,
):
    fecha_inicio = datetime.utcnow() - timedelta(days=days)

    stmt = (
        select(
            Cerveza.tipo,
            func.sum(Venta.cantidad_ml).label("total_ml"),
        )
        .join(Venta, Venta.id_cerveza == Cerveza.id)
        .join(Equipo, Venta.id_equipo == Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(Venta.fecha_hora >= fecha_inicio, PuntoVenta.tenant_id == tenant.id, Cerveza.tenant_id == tenant.id)
        .group_by(Cerveza.tipo)
        .order_by(func.sum(Venta.cantidad_ml).desc())
    )
    rows = session.exec(stmt).all()
    total_ml = sum((row[1] or 0) for row in rows) or 0

    datos = []
    for tipo, ml in rows:
        ml_value = float(ml or 0)
        porcentaje = (ml_value / float(total_ml)) * 100.0 if total_ml else 0.0
        datos.append(
            {
                "estilo": tipo,
                "litros": round(ml_value / 1000.0, 2),
                "porcentaje": round(porcentaje, 1),
            }
        )

    return {"periodo_dias": days, "datos": datos}


@router.get("/canillas")
def get_canillas(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
    limit: int = 6,
):
    stmt = (
        select(
            Equipo.id,
            Equipo.nombre_equipo,
            Equipo.capacidad_actual,
            TipoBarril.capacidad,
            Cerveza.nombre,
            TipoEstadoEquipo.permite_ventas,
        )
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .join(TipoBarril, TipoBarril.id == Equipo.id_barril)
        .join(TipoEstadoEquipo, TipoEstadoEquipo.id == Equipo.id_estado_equipo)
        .join(Cerveza, Cerveza.id == Equipo.id_cerveza, isouter=True)
        .where(PuntoVenta.tenant_id == tenant.id)
        .order_by(Equipo.id.asc())
        .limit(limit)
    )
    rows = session.exec(stmt).all()

    canillas = []
    for equipo_id, nombre_equipo, capacidad_actual, capacidad_total, cerveza_nombre, permite_ventas in rows:
        total = float(capacidad_total or 0)
        actual = float(capacidad_actual or 0)
        pct = round((actual / total) * 100.0) if total > 0 else 0

        if not permite_ventas:
            estado = "critical"
        elif pct >= 50:
            estado = "active"
        elif pct >= 20:
            estado = "warning"
        else:
            estado = "critical"

        canillas.append(
            {
                "id": equipo_id,
                "nombre": nombre_equipo or f"Canilla {equipo_id}",
                "cerveza": cerveza_nombre or "Sin asignar",
                "nivel_pct": int(pct),
                "estado": estado,
            }
        )

    return {"canillas": canillas}


@router.get("/metodos-pago-hoy")
def get_metodos_pago_hoy(
    current_user: Annotated[Usuario, Depends(get_current_active_user)],
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    now = datetime.utcnow()
    inicio = datetime(now.year, now.month, now.day)
    fin = inicio + timedelta(days=1)

    stmt = (
        select(
            TipoMetodoPago.metodo_pago,
            func.sum(Pago.monto).label("monto"),
        )
        .join(Venta, (Venta.id == Pago.id_venta) & (Venta.fecha_hora == Pago.fecha_venta))
        .join(Equipo, Venta.id_equipo == Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .join(TipoMetodoPago, TipoMetodoPago.id == Pago.id_metodo_pago)
        .where(
            Pago.fecha_pago >= inicio,
            Pago.fecha_pago < fin,
            Pago.estado == TipoEstadoPago.APROBADO,
            PuntoVenta.tenant_id == tenant.id,
        )
        .group_by(TipoMetodoPago.metodo_pago)
        .order_by(func.sum(Pago.monto).desc())
    )
    rows = session.exec(stmt).all()
    total = sum((float(row[1] or 0) for row in rows)) or 0.0

    datos = []
    for metodo, monto in rows:
        monto_value = float(monto or 0)
        porcentaje = (monto_value / total) * 100.0 if total > 0 else 0.0
        datos.append(
            {
                "metodo": metodo,
                "monto": round(monto_value, 2),
                "porcentaje": round(porcentaje, 0),
            }
        )

    return {"total": round(total, 2), "metodos": datos}
