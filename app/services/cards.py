from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from sqlmodel import Session, select

from app.core.security import hmac_sha256_hex
from app.core.config import settings
from app.models.cards import Card, CardAssignment
from app.models.user_extended import Usuario


class CardService:
    @staticmethod
    def _hash_uid(uid: str) -> str:
        secret = settings.device_uid_hmac_secret or settings.secret_key
        return hmac_sha256_hex(uid.strip(), secret=secret)

    @staticmethod
    def hash_uid(uid: str) -> str:
        return CardService._hash_uid(uid)

    @staticmethod
    def lookup(session: Session, *, tenant_id: int, uid: str) -> Tuple[Optional[Card], Optional[CardAssignment], Optional[Usuario]]:
        uid_hash = CardService._hash_uid(uid)
        card = session.exec(select(Card).where(Card.uid_hash == uid_hash, Card.tenant_id == tenant_id, Card.activo == True)).first()
        if not card:
            return None, None, None

        assignment = session.exec(
            select(CardAssignment).where(
                CardAssignment.card_id == card.id,
                CardAssignment.tenant_id == tenant_id,
                CardAssignment.activo == True,
            )
        ).first()
        user = None
        if assignment and assignment.user_id:
            user = session.exec(
                select(Usuario).where(Usuario.id == assignment.user_id, Usuario.tenant_id == tenant_id, Usuario.activo == True)
            ).first()
        return card, assignment, user

    @staticmethod
    def bind_to_user(
        session: Session,
        *,
        tenant_id: int,
        uid: str,
        user_id_ext: Optional[str],
        codigo_cliente: Optional[str],
        assigned_by: int,
    ) -> Card:
        if not user_id_ext and not codigo_cliente:
            raise ValueError("USER_IDENTIFIER_REQUIRED")

        user = None
        if user_id_ext:
            user = session.exec(select(Usuario).where(Usuario.id_ext == user_id_ext, Usuario.tenant_id == tenant_id, Usuario.activo == True)).first()
        if not user and codigo_cliente:
            user = session.exec(
                select(Usuario).where(Usuario.codigo_cliente == codigo_cliente, Usuario.tenant_id == tenant_id, Usuario.activo == True)
            ).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        uid_hash = CardService._hash_uid(uid)
        card = session.exec(select(Card).where(Card.uid_hash == uid_hash, Card.activo == True)).first()
        if not card:
            card = Card(tenant_id=tenant_id, uid_hash=uid_hash, activo=True)
            session.add(card)
            session.flush()
        elif card.tenant_id != tenant_id:
            raise ValueError("UID_OTHER_TENANT")

        active_assignment = session.exec(
            select(CardAssignment).where(
                CardAssignment.card_id == card.id,
                CardAssignment.activo == True,
            )
        ).first()
        if active_assignment and active_assignment.user_id and active_assignment.user_id != user.id:
            raise ValueError("UID_ALREADY_ASSIGNED")

        if active_assignment and active_assignment.activo:
            active_assignment.activo = False
            active_assignment.unassigned_at = datetime.utcnow()
            session.add(active_assignment)

        assignment = CardAssignment(
            tenant_id=tenant_id,
            card_id=card.id,
            user_id=user.id,
            assignment_type="becard",
            activo=True,
            assigned_by=assigned_by,
        )
        session.add(assignment)
        session.commit()
        session.refresh(card)
        return card

    @staticmethod
    def issue_anonymous(
        session: Session,
        *,
        tenant_id: int,
        uid: str,
        assigned_by: int,
    ) -> Card:
        uid_hash = CardService._hash_uid(uid)
        card = session.exec(select(Card).where(Card.uid_hash == uid_hash, Card.activo == True)).first()
        if not card:
            card = Card(tenant_id=tenant_id, uid_hash=uid_hash, activo=True)
            session.add(card)
            session.flush()
        elif card.tenant_id != tenant_id:
            raise ValueError("UID_OTHER_TENANT")

        active_assignment = session.exec(
            select(CardAssignment).where(
                CardAssignment.card_id == card.id,
                CardAssignment.activo == True,
            )
        ).first()
        if active_assignment and active_assignment.user_id:
            raise ValueError("UID_ALREADY_ASSIGNED")
        if active_assignment and active_assignment.assignment_type == "anonymous_wallet":
            return card

        if active_assignment:
            active_assignment.activo = False
            session.add(active_assignment)

        assignment = CardAssignment(
            tenant_id=tenant_id,
            card_id=card.id,
            user_id=None,
            assignment_type="anonymous_wallet",
            activo=True,
            assigned_by=assigned_by,
        )
        session.add(assignment)
        session.commit()
        session.refresh(card)
        return card
