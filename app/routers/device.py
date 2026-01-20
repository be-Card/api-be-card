from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel

from app.core.database import get_session
from app.core.tenant import get_current_tenant
from app.models.tenant import Tenant
from app.models.user_extended import Usuario
from app.routers.auth import get_current_active_user
from app.services.cards import CardService
from app.services.device_sessions import DeviceSessionService
from app.services.equipos import EquipoService


router = APIRouter(prefix="/device", tags=["device"])
logger = logging.getLogger(__name__)


class DeviceSessionCreateRequest(SQLModel):
    equipo_id: Optional[int] = None
    equipo_id_ext: Optional[UUID] = None
    equipo_codigo: Optional[str] = None
    uid: Optional[str] = None
    uid_hash: Optional[str] = None
    requested_ml: int
    payment_mode: str = "wallet"
    idempotency_key: Optional[str] = None
    user_id: Optional[int] = None


class DeviceSessionBeer(SQLModel):
    id: int


class DeviceSessionCreateResponse(SQLModel):
    session_id: str
    cerveza: DeviceSessionBeer
    price_per_liter: Decimal
    price_per_ml: Decimal
    max_ml: int
    estimated_amount: Decimal


class DeviceSessionCompleteRequest(SQLModel):
    poured_ml: int
    payment_method_name: Optional[str] = None
    provider_transaction_id: Optional[str] = None


class DeviceSessionCompleteResponse(SQLModel):
    session_id: str
    status: str
    poured_ml: int
    final_amount: Decimal


@router.post("/sessions", response_model=DeviceSessionCreateResponse, status_code=201)
def create_device_session(
    payload: DeviceSessionCreateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    try:
        equipo_id = EquipoService.resolve_equipo_id(
            session,
            tenant_id=tenant.id,
            equipo_id=payload.equipo_id,
            equipo_id_ext=payload.equipo_id_ext,
            equipo_codigo=payload.equipo_codigo,
        )
        uid_hash = payload.uid_hash
        user_id = payload.user_id
        if payload.uid:
            uid_hash = CardService.hash_uid(payload.uid)
            _, assignment, _ = CardService.lookup(session, tenant_id=tenant.id, uid=payload.uid)
            if assignment and assignment.user_id:
                user_id = int(assignment.user_id)

        device_session = DeviceSessionService.create_session(
            session,
            tenant_id=tenant.id,
            equipo_id=equipo_id,
            uid_hash=uid_hash,
            requested_ml=payload.requested_ml,
            payment_mode=payload.payment_mode,
            idempotency_key=payload.idempotency_key,
            user_id=user_id,
        )
    except ValueError as e:
        code = str(e)
        if code == "EQUIPO_REFERENCE_REQUIRED":
            raise HTTPException(status_code=400, detail="Falta identificar el equipo")
        if code == "EQUIPO_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        if code == "EQUIPO_OR_BEER_NOT_CONFIGURED":
            raise HTTPException(status_code=400, detail="Equipo sin cerveza configurada o inválido")
        if code == "Cerveza no encontrada" or code == "Precio base no encontrado para la cerveza":
            raise HTTPException(status_code=404, detail="No se encontró un precio aplicable")
        raise HTTPException(status_code=400, detail="No se pudo crear la sesión")
    except Exception:
        logger.exception("Error creando sesión device", extra={"equipo_id": payload.equipo_id})
        raise HTTPException(status_code=500, detail="Error interno")

    price_per_ml = (Decimal(str(device_session.price_per_liter)) / Decimal(1000)).quantize(Decimal("0.0001"))
    return DeviceSessionCreateResponse(
        session_id=str(device_session.id_ext),
        cerveza=DeviceSessionBeer(id=device_session.cerveza_id),
        price_per_liter=device_session.price_per_liter,
        price_per_ml=price_per_ml,
        max_ml=device_session.max_ml,
        estimated_amount=device_session.estimated_amount,
    )


@router.post("/sessions/{session_id}/complete", response_model=DeviceSessionCompleteResponse)
def complete_device_session(
    session_id: str,
    payload: DeviceSessionCompleteRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    try:
        device_session = DeviceSessionService.complete_wallet_session(
            session,
            tenant_id=tenant.id,
            session_id_ext=session_id,
            poured_ml=payload.poured_ml,
            created_by=current_user.id,
        )
    except ValueError as e:
        code = str(e)
        if code == "INVALID_PAYMENT_MODE":
            try:
                device_session = DeviceSessionService.complete_external_session(
                    session,
                    tenant_id=tenant.id,
                    session_id_ext=session_id,
                    poured_ml=payload.poured_ml,
                    payment_method_name=payload.payment_method_name or "Mercado Pago",
                    provider_transaction_id=payload.provider_transaction_id,
                )
            except ValueError as e2:
                code2 = str(e2)
                if code2 == "SESSION_NOT_FOUND":
                    raise HTTPException(status_code=404, detail="Sesión no encontrada")
                if code2 == "INVALID_PAYMENT_MODE":
                    raise HTTPException(status_code=400, detail="Modo de pago inválido para esta sesión")
                raise HTTPException(status_code=400, detail="No se pudo completar la sesión")
        elif code == "SESSION_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        elif code == "USER_REQUIRED":
            raise HTTPException(status_code=400, detail="Falta identificar el usuario para pagar con saldo")
        elif code == "INSUFFICIENT_FUNDS":
            raise HTTPException(status_code=402, detail="Saldo insuficiente")
        else:
            raise HTTPException(status_code=400, detail="No se pudo completar la sesión")
    except Exception:
        logger.exception("Error completando sesión device", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="Error interno")

    return DeviceSessionCompleteResponse(
        session_id=str(device_session.id_ext),
        status=device_session.status,
        poured_ml=int(device_session.poured_ml or 0),
        final_amount=device_session.final_amount or Decimal("0.00"),
    )
