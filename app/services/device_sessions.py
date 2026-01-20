from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlmodel import Session, select

from app.models.cards import Card, CardAssignment
from app.models.device_session import DeviceSession
from app.models.points import CalculadoraPuntos, ReglaConversionPuntos
from app.models.pricing import ConsultaPrecio
from app.models.sales import Venta
from app.models.sales_point import Equipo, PuntoVenta
from app.models.transactions import Pago, TipoEstadoPago, TransaccionPuntos
from app.models.user_extended import TipoMetodoPago, UsuarioNivel
from app.services.pricing import PricingService
from app.services.wallets import WalletService


class DeviceSessionService:
    @staticmethod
    def create_session(
        session: Session,
        *,
        tenant_id: int,
        equipo_id: int,
        uid_hash: Optional[str],
        requested_ml: int,
        payment_mode: str,
        idempotency_key: Optional[str],
        user_id: Optional[int],
    ) -> DeviceSession:
        if idempotency_key:
            existing = session.exec(
                select(DeviceSession).where(
                    DeviceSession.tenant_id == tenant_id,
                    DeviceSession.equipo_id == equipo_id,
                    DeviceSession.idempotency_key == idempotency_key,
                    DeviceSession.status == "created",
                )
            ).first()
            if existing:
                return existing

        equipo = session.exec(
            select(Equipo)
            .join(PuntoVenta, Equipo.id_punto_de_venta == PuntoVenta.id)
            .where(
                Equipo.id == equipo_id,
                Equipo.activo == True,
                PuntoVenta.tenant_id == tenant_id,
                PuntoVenta.activo == True,
            )
        ).first()
        if not equipo or not equipo.id_cerveza:
            raise ValueError("EQUIPO_OR_BEER_NOT_CONFIGURED")

        consulta = ConsultaPrecio(
            id_cerveza=equipo.id_cerveza,
            id_equipo=equipo.id,
            id_punto_venta=equipo.id_punto_de_venta,
            fecha_consulta=datetime.utcnow(),
            cantidad=1,
        )
        calculo = PricingService.calcular_precio(session, consulta, tenant_id=tenant_id)
        price_per_liter = Decimal(str(calculo.precio_final))
        estimated_amount = (Decimal(requested_ml) / Decimal(1000)) * price_per_liter
        estimated_amount = estimated_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        max_ml = requested_ml
        if payment_mode == "wallet":
            if user_id:
                wallet = WalletService.get_or_create_user_wallet(session, tenant_id=tenant_id, user_id=user_id)
                if Decimal(str(wallet.balance)) <= 0:
                    max_ml = 0
                else:
                    max_ml_by_balance = int((Decimal(str(wallet.balance)) / price_per_liter) * Decimal(1000))
                    max_ml = max(0, min(int(requested_ml), int(max_ml_by_balance)))
            elif uid_hash:
                card = session.exec(select(Card).where(Card.uid_hash == uid_hash, Card.activo == True)).first()
                if card:
                    assignment = session.exec(
                        select(CardAssignment).where(
                            CardAssignment.tenant_id == tenant_id,
                            CardAssignment.card_id == card.id,
                            CardAssignment.activo == True,
                        )
                    ).first()
                    if assignment and assignment.assignment_type == "anonymous_wallet" and assignment.user_id is None:
                        wallet = WalletService.get_or_create_card_wallet(session, tenant_id=tenant_id, card_id=card.id)
                        if Decimal(str(wallet.balance)) <= 0:
                            max_ml = 0
                        else:
                            max_ml_by_balance = int((Decimal(str(wallet.balance)) / price_per_liter) * Decimal(1000))
                            max_ml = max(0, min(int(requested_ml), int(max_ml_by_balance)))

        device_session = DeviceSession(
            tenant_id=tenant_id,
            equipo_id=equipo.id,
            uid_hash=uid_hash,
            user_id=user_id,
            cerveza_id=equipo.id_cerveza,
            price_per_liter=price_per_liter.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            requested_ml=requested_ml,
            max_ml=max_ml,
            estimated_amount=estimated_amount,
            payment_mode=payment_mode,
            idempotency_key=idempotency_key,
        )
        session.add(device_session)
        session.commit()
        session.refresh(device_session)
        return device_session

    @staticmethod
    def complete_wallet_session(
        session: Session,
        *,
        tenant_id: int,
        session_id_ext: str,
        poured_ml: int,
        created_by: Optional[int],
    ) -> DeviceSession:
        device_session = session.exec(
            select(DeviceSession).where(
                DeviceSession.tenant_id == tenant_id,
                DeviceSession.id_ext == session_id_ext,
            )
        ).first()
        if not device_session:
            raise ValueError("SESSION_NOT_FOUND")

        if device_session.status == "completed":
            return device_session

        if device_session.payment_mode != "wallet":
            raise ValueError("INVALID_PAYMENT_MODE")

        poured_ml_capped = max(0, min(int(poured_ml), int(device_session.max_ml)))
        final_amount = (Decimal(poured_ml_capped) / Decimal(1000)) * Decimal(str(device_session.price_per_liter))
        final_amount = final_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if device_session.user_id:
            wallet = WalletService.get_or_create_user_wallet(session, tenant_id=tenant_id, user_id=int(device_session.user_id))
            WalletService.debit(
                session,
                wallet_id=wallet.id,
                amount=final_amount,
                reference_type="device_session",
                reference_id=str(device_session.id_ext),
                idempotency_key=f"device_session:{device_session.id_ext}",
                created_by=created_by,
            )
        else:
            if not device_session.uid_hash:
                raise ValueError("USER_REQUIRED")
            card = session.exec(select(Card).where(Card.uid_hash == device_session.uid_hash, Card.activo == True)).first()
            if not card:
                raise ValueError("USER_REQUIRED")
            assignment = session.exec(
                select(CardAssignment).where(
                    CardAssignment.tenant_id == tenant_id,
                    CardAssignment.card_id == card.id,
                    CardAssignment.activo == True,
                )
            ).first()
            if not assignment or assignment.assignment_type != "anonymous_wallet" or assignment.user_id is not None:
                raise ValueError("USER_REQUIRED")
            wallet = WalletService.get_or_create_card_wallet(session, tenant_id=tenant_id, card_id=card.id)
            WalletService.debit(
                session,
                wallet_id=wallet.id,
                amount=final_amount,
                reference_type="device_session",
                reference_id=str(device_session.id_ext),
                idempotency_key=f"device_session:{device_session.id_ext}",
                created_by=created_by,
            )

        from uuid import uuid4

        venta = Venta(
            id_ext=str(uuid4()),
            fecha_hora=datetime.utcnow(),
            cantidad_ml=poured_ml_capped,
            monto_total=final_amount,
            descuento_aplicado=Decimal("0.00"),
            id_usuario=int(device_session.user_id) if device_session.user_id else None,
            id_cerveza=int(device_session.cerveza_id),
            id_equipo=int(device_session.equipo_id),
        )
        session.add(venta)
        session.flush()

        metodo = session.exec(select(TipoMetodoPago).where(TipoMetodoPago.metodo_pago == "Saldo BeCard")).first()
        if not metodo:
            metodo = TipoMetodoPago(metodo_pago="Saldo BeCard", activo=True, requiere_autorizacion=False)
            session.add(metodo)
            session.flush()

        pago = Pago(
            id_venta=int(venta.id),
            fecha_venta=venta.fecha_hora,
            id_metodo_pago=int(metodo.id),
            monto=final_amount,
            estado=TipoEstadoPago.APROBADO,
            id_transaccion_proveedor=str(device_session.id_ext),
        )
        session.add(pago)

        if device_session.user_id:
            now = datetime.utcnow()
            reglas = session.exec(
                select(ReglaConversionPuntos).where(
                    ReglaConversionPuntos.activo == True,
                    ReglaConversionPuntos.fecha_inicio <= now,
                    (ReglaConversionPuntos.fecha_fin == None) | (ReglaConversionPuntos.fecha_fin >= now),
                )
            ).all()
            calculo_puntos = CalculadoraPuntos.calcular_puntos(final_amount, list(reglas))

            nivel = session.exec(select(UsuarioNivel).where(UsuarioNivel.id_usuario == int(device_session.user_id))).first()
            if not nivel:
                nivel = UsuarioNivel(id_usuario=int(device_session.user_id), id_nivel=1, puntaje_actual=0)
                session.add(nivel)
                session.flush()

            saldo_anterior = int(nivel.puntaje_actual or 0)
            saldo_posterior = max(0, saldo_anterior + int(calculo_puntos.puntos_ganados))
            nivel.puntaje_actual = saldo_posterior
            session.add(nivel)

            tx_puntos = TransaccionPuntos(
                id_usuario=int(device_session.user_id),
                puntos_ganados=int(calculo_puntos.puntos_ganados),
                puntos_canjeados=0,
                saldo_anterior=max(0, saldo_anterior),
                saldo_posterior=max(0, saldo_posterior),
                id_venta=int(venta.id),
                descripcion=f"Venta {venta.id_ext}",
                tipo_transaccion="venta",
            )
            session.add(tx_puntos)

        device_session.poured_ml = poured_ml_capped
        device_session.final_amount = final_amount
        device_session.status = "completed"
        device_session.completed_at = datetime.utcnow()
        device_session.venta_id = int(venta.id)
        device_session.venta_fecha_hora = venta.fecha_hora
        session.add(device_session)

        session.commit()
        session.refresh(device_session)
        return device_session

    @staticmethod
    def complete_external_session(
        session: Session,
        *,
        tenant_id: int,
        session_id_ext: str,
        poured_ml: int,
        payment_method_name: str,
        provider_transaction_id: Optional[str],
    ) -> DeviceSession:
        device_session = session.exec(
            select(DeviceSession).where(
                DeviceSession.tenant_id == tenant_id,
                DeviceSession.id_ext == session_id_ext,
            )
        ).first()
        if not device_session:
            raise ValueError("SESSION_NOT_FOUND")

        if device_session.status in ("completed", "pending_payment"):
            return device_session

        if device_session.payment_mode != "external":
            raise ValueError("INVALID_PAYMENT_MODE")

        poured_ml_capped = max(0, min(int(poured_ml), int(device_session.max_ml)))
        final_amount = (Decimal(poured_ml_capped) / Decimal(1000)) * Decimal(str(device_session.price_per_liter))
        final_amount = final_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        from uuid import uuid4

        venta = Venta(
            id_ext=str(uuid4()),
            fecha_hora=datetime.utcnow(),
            cantidad_ml=poured_ml_capped,
            monto_total=final_amount,
            descuento_aplicado=Decimal("0.00"),
            id_usuario=int(device_session.user_id) if device_session.user_id else None,
            id_cerveza=int(device_session.cerveza_id),
            id_equipo=int(device_session.equipo_id),
        )
        session.add(venta)
        session.flush()

        metodo = session.exec(select(TipoMetodoPago).where(TipoMetodoPago.metodo_pago == payment_method_name)).first()
        if not metodo:
            metodo = TipoMetodoPago(metodo_pago=payment_method_name, activo=True, requiere_autorizacion=True)
            session.add(metodo)
            session.flush()

        pago = Pago(
            id_venta=int(venta.id),
            fecha_venta=venta.fecha_hora,
            id_metodo_pago=int(metodo.id),
            monto=final_amount,
            estado=TipoEstadoPago.PENDIENTE,
            id_transaccion_proveedor=provider_transaction_id or str(device_session.id_ext),
        )
        session.add(pago)
        session.flush()

        device_session.poured_ml = poured_ml_capped
        device_session.final_amount = final_amount
        device_session.status = "pending_payment"
        device_session.completed_at = datetime.utcnow()
        device_session.venta_id = int(venta.id)
        device_session.venta_fecha_hora = venta.fecha_hora
        device_session.pago_id = int(pago.id)
        session.add(device_session)

        session.commit()
        session.refresh(device_session)
        return device_session

    @staticmethod
    def complete_session(
        session: Session,
        *,
        tenant_id: int,
        session_id_ext: str,
        poured_ml: int,
    ) -> DeviceSession:
        device_session = session.exec(
            select(DeviceSession).where(
                DeviceSession.tenant_id == tenant_id,
                DeviceSession.id_ext == session_id_ext,
            )
        ).first()
        if not device_session:
            raise ValueError("SESSION_NOT_FOUND")

        if device_session.status == "completed":
            return device_session

        poured_ml_capped = max(0, min(int(poured_ml), int(device_session.max_ml)))
        final_amount = (Decimal(poured_ml_capped) / Decimal(1000)) * Decimal(str(device_session.price_per_liter))
        final_amount = final_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        device_session.poured_ml = poured_ml_capped
        device_session.final_amount = final_amount
        device_session.status = "completed"
        device_session.completed_at = datetime.utcnow()

        session.add(device_session)
        session.commit()
        session.refresh(device_session)
        return device_session
