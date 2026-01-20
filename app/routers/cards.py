from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel

from app.core.database import get_session
from app.core.tenant import get_current_tenant
from app.models.tenant import Tenant
from app.models.user_extended import Usuario
from app.routers.auth import get_current_active_user, require_admin_or_socio
from app.services.cards import CardService
from app.services.wallets import WalletService


router = APIRouter(prefix="/cards", tags=["cards"])
logger = logging.getLogger(__name__)


class CardLookupRequest(SQLModel):
    uid: str


class CardLookupResponse(SQLModel):
    card_status: str
    card_id: Optional[int] = None
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    assignment_type: Optional[str] = None
    balance: Optional[str] = None


class CardBindRequest(SQLModel):
    uid: str
    user_id_ext: Optional[str] = None
    codigo_cliente: Optional[str] = None


class CardBindResponse(SQLModel):
    card_id: int
    message: str


class CardIssueAnonymousRequest(SQLModel):
    uid: str


class CardIssueAnonymousResponse(SQLModel):
    card_id: int
    message: str


@router.post("/lookup", response_model=CardLookupResponse)
def lookup_card(
    payload: CardLookupRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    card, assignment, user = CardService.lookup(session, tenant_id=tenant.id, uid=payload.uid)
    if not card:
        return CardLookupResponse(card_status="unknown")

    if assignment and assignment.user_id and user:
        wallet = WalletService.get_or_create_user_wallet(session, tenant_id=tenant.id, user_id=user.id)
        display_name = f"{user.nombres} {user.apellidos}".strip()
        return CardLookupResponse(
            card_status="assigned_user",
            card_id=card.id,
            user_id=user.id,
            display_name=display_name,
            assignment_type=assignment.assignment_type,
            balance=str(wallet.balance),
        )

    if assignment and assignment.assignment_type == "anonymous_wallet":
        wallet = WalletService.get_or_create_card_wallet(session, tenant_id=tenant.id, card_id=card.id)
        return CardLookupResponse(
            card_status="anonymous_wallet",
            card_id=card.id,
            assignment_type=assignment.assignment_type,
            balance=str(wallet.balance),
        )

    return CardLookupResponse(card_status="unknown", card_id=card.id)


@router.post("/bind", response_model=CardBindResponse, status_code=status.HTTP_201_CREATED)
def bind_card(
    payload: CardBindRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(require_admin_or_socio),
    session: Session = Depends(get_session),
):
    try:
        card = CardService.bind_to_user(
            session,
            tenant_id=tenant.id,
            uid=payload.uid,
            user_id_ext=payload.user_id_ext,
            codigo_cliente=payload.codigo_cliente,
            assigned_by=current_user.id,
        )
    except ValueError as e:
        code = str(e)
        if code == "USER_IDENTIFIER_REQUIRED":
            raise HTTPException(status_code=400, detail="Falta identificar el usuario (user_id_ext o codigo_cliente)")
        if code == "USER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if code == "UID_ALREADY_ASSIGNED":
            raise HTTPException(status_code=409, detail="La tarjeta ya está asignada a otro usuario")
        if code == "UID_OTHER_TENANT":
            raise HTTPException(status_code=409, detail="La tarjeta pertenece a otro establecimiento")
        raise HTTPException(status_code=400, detail="No se pudo vincular la tarjeta")
    except Exception:
        logger.exception("Error vinculando tarjeta")
        raise HTTPException(status_code=500, detail="Error interno")

    return CardBindResponse(card_id=card.id, message="Tarjeta vinculada")


@router.post("/issue-anonymous", response_model=CardIssueAnonymousResponse, status_code=status.HTTP_201_CREATED)
def issue_anonymous_card(
    payload: CardIssueAnonymousRequest,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: Usuario = Depends(require_admin_or_socio),
    session: Session = Depends(get_session),
):
    try:
        card = CardService.issue_anonymous(session, tenant_id=tenant.id, uid=payload.uid, assigned_by=current_user.id)
    except ValueError as e:
        if str(e) == "UID_ALREADY_ASSIGNED":
            raise HTTPException(status_code=409, detail="La tarjeta ya está asignada a un usuario registrado")
        if str(e) == "UID_OTHER_TENANT":
            raise HTTPException(status_code=409, detail="La tarjeta pertenece a otro establecimiento")
        raise HTTPException(status_code=400, detail="No se pudo emitir la tarjeta")
    except Exception:
        logger.exception("Error emitiendo tarjeta anónima")
        raise HTTPException(status_code=500, detail="Error interno")

    return CardIssueAnonymousResponse(card_id=card.id, message="Tarjeta emitida")
