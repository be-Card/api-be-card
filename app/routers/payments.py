from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

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


router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentConfirmRequest(SQLModel):
    provider_transaction_id: str
    status: TipoEstadoPago
    motivo_rechazo: Optional[str] = None


class PaymentConfirmResponse(SQLModel):
    message: str


@router.post("/confirm", response_model=PaymentConfirmResponse, status_code=status.HTTP_200_OK)
def confirm_payment(
    payload: PaymentConfirmRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    from sqlalchemy import and_

    pago = session.exec(
        select(Pago)
        .join(Venta, and_(Venta.id == Pago.id_venta, Venta.fecha_hora == Pago.fecha_venta))
        .join(Equipo, Venta.id_equipo == Equipo.id)
        .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
        .where(Pago.id_transaccion_proveedor == payload.provider_transaction_id, PuntoVenta.tenant_id == tenant.id)
    ).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    pago.estado = payload.status
    pago.fecha_actualizacion = datetime.utcnow()
    pago.motivo_rechazo = payload.motivo_rechazo
    session.add(pago)

    if payload.status == TipoEstadoPago.APROBADO:
        venta = session.exec(select(Venta).where(Venta.id == pago.id_venta, Venta.fecha_hora == pago.fecha_venta)).first()
        if venta and venta.id_usuario:
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

                nivel = session.exec(select(UsuarioNivel).where(UsuarioNivel.id_usuario == int(venta.id_usuario))).first()
                if not nivel:
                    nivel = UsuarioNivel(id_usuario=int(venta.id_usuario), id_nivel=1, puntaje_actual=0)
                    session.add(nivel)
                    session.flush()

                saldo_anterior = int(nivel.puntaje_actual or 0)
                saldo_posterior = max(0, saldo_anterior + int(calculo.puntos_ganados))
                nivel.puntaje_actual = saldo_posterior
                session.add(nivel)

                tx = TransaccionPuntos(
                    id_usuario=int(venta.id_usuario),
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
    return PaymentConfirmResponse(message="Pago actualizado")
