from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models.cards import Card, CardAssignment
from app.services.wallets import WalletService


class WalletTopupService:
    @staticmethod
    def topup_anonymous_card(
        session: Session,
        *,
        tenant_id: int,
        card_id: int,
        amount: Decimal,
        created_by: int,
    ) -> None:
        card = session.exec(select(Card).where(Card.id == card_id, Card.activo == True)).first()
        if not card:
            raise ValueError("CARD_NOT_FOUND")
        if card.tenant_id != tenant_id:
            raise ValueError("CARD_NOT_FOUND")

        assignment = session.exec(
            select(CardAssignment).where(
                CardAssignment.tenant_id == tenant_id,
                CardAssignment.card_id == card.id,
                CardAssignment.activo == True,
            )
        ).first()
        if not assignment or assignment.assignment_type != "anonymous_wallet" or assignment.user_id is not None:
            raise ValueError("CARD_NOT_ANONYMOUS")

        wallet = WalletService.get_or_create_card_wallet(session, tenant_id=tenant_id, card_id=card.id)
        WalletService.credit(
            session,
            wallet_id=wallet.id,
            amount=amount,
            reference_type="topup",
            reference_id=f"card:{card.id}",
            idempotency_key=None,
            created_by=created_by,
        )
        session.commit()
