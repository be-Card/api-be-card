from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel

from app.core.database import get_session
from app.core.tenant import get_current_tenant
from app.models.tenant import Tenant
from app.models.user_extended import Usuario
from app.routers.auth import require_admin_or_socio
from app.services.wallet_topups import WalletTopupService


router = APIRouter(prefix="/wallets", tags=["wallets"])
logger = logging.getLogger(__name__)


class AnonymousTopupRequest(SQLModel):
    amount: Decimal


class AnonymousTopupResponse(SQLModel):
    message: str


@router.post("/anonymous/{card_id}/topup", response_model=AnonymousTopupResponse, status_code=status.HTTP_201_CREATED)
def topup_anonymous_card(
    card_id: int,
    payload: AnonymousTopupRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(require_admin_or_socio),
    session: Session = Depends(get_session),
):
    try:
        WalletTopupService.topup_anonymous_card(
            session,
            tenant_id=tenant.id,
            card_id=card_id,
            amount=payload.amount,
            created_by=current_user.id,
        )
    except ValueError as e:
        code = str(e)
        if code == "CARD_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
        if code == "CARD_NOT_ANONYMOUS":
            raise HTTPException(status_code=400, detail="La tarjeta no es anónima")
        raise HTTPException(status_code=400, detail="No se pudo cargar saldo")
    except Exception:
        logger.exception("Error cargando saldo a tarjeta anónima", extra={"card_id": card_id})
        raise HTTPException(status_code=500, detail="Error interno")

    return AnonymousTopupResponse(message="Saldo cargado")
