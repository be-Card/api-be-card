from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.tenant import get_current_tenant
from app.models.points import CalculadoraPuntos, ReglaConversionPuntos
from app.models.sales import Venta
from app.models.sales_point import Equipo, PuntoVenta
from app.models.tenant import Tenant
from app.models.transactions import Pago, TipoEstadoPago, TransaccionPuntos
from app.models.user_extended import Usuario, UsuarioNivel
from app.routers.auth import get_current_active_user


router = APIRouter(prefix="/sales", tags=["sales"])


class SaleClaimResponse(SQLModel):
    message: str


@router.post("/{sale_id_ext}/claim", response_model=SaleClaimResponse, status_code=status.HTTP_200_OK)
def claim_sale(
    sale_id_ext: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    venta = session.exec(
        select(Venta)
        .join(Equipo, Venta.id_equipo == Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(Venta.id_ext == sale_id_ext, PuntoVenta.tenant_id == tenant.id)
    ).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    if venta.id_usuario and int(venta.id_usuario) != int(current_user.id):
        raise HTTPException(status_code=409, detail="La venta ya pertenece a otro usuario")

    if not venta.id_usuario:
        venta.id_usuario = int(current_user.id)
        session.add(venta)

    pago = session.exec(
        select(Pago)
        .where(Pago.id_venta == int(venta.id), Pago.fecha_venta == venta.fecha_hora)
        .order_by(Pago.fecha_pago.desc())
    ).first()

    if pago and pago.estado == TipoEstadoPago.APROBADO:
        already = session.exec(
            select(TransaccionPuntos.id).where(
                TransaccionPuntos.id_venta == int(venta.id),
                TransaccionPuntos.tipo_transaccion == "venta",
            )
        ).first()
        if not already:
            now = datetime.utcnow()
            reglas = session.exec(
                select(ReglaConversionPuntos).where(
                    ReglaConversionPuntos.activo == True,
                    ReglaConversionPuntos.fecha_inicio <= now,
                    (ReglaConversionPuntos.fecha_fin == None) | (ReglaConversionPuntos.fecha_fin >= now),
                )
            ).all()
            calculo = CalculadoraPuntos.calcular_puntos(Decimal(str(venta.monto_total)), list(reglas))

            nivel = session.exec(select(UsuarioNivel).where(UsuarioNivel.id_usuario == int(current_user.id))).first()
            if not nivel:
                nivel = UsuarioNivel(id_usuario=int(current_user.id), id_nivel=1, puntaje_actual=0)
                session.add(nivel)
                session.flush()

            saldo_anterior = int(nivel.puntaje_actual or 0)
            saldo_posterior = max(0, saldo_anterior + int(calculo.puntos_ganados))
            nivel.puntaje_actual = saldo_posterior
            session.add(nivel)

            tx = TransaccionPuntos(
                id_usuario=int(current_user.id),
                puntos_ganados=int(calculo.puntos_ganados),
                puntos_canjeados=0,
                saldo_anterior=max(0, saldo_anterior),
                saldo_posterior=max(0, saldo_posterior),
                id_venta=int(venta.id),
                descripcion=f"Venta {venta.id_ext}",
                tipo_transaccion="venta",
            )
            session.add(tx)

    session.commit()
    return SaleClaimResponse(message="Venta reclamada")
