from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlmodel import Session, select

from app.models.wallet import Wallet, WalletTxn


class WalletService:
    @staticmethod
    def get_or_create_user_wallet(session: Session, *, tenant_id: int, user_id: int) -> Wallet:
        wallet = session.exec(
            select(Wallet).where(
                Wallet.tenant_id == tenant_id,
                Wallet.owner_type == "user",
                Wallet.owner_user_id == user_id,
                Wallet.activo == True,
            )
        ).first()
        if wallet:
            return wallet

        wallet = Wallet(tenant_id=tenant_id, owner_type="user", owner_user_id=user_id, balance=Decimal("0.00"), activo=True)
        session.add(wallet)
        session.commit()
        session.refresh(wallet)
        return wallet

    @staticmethod
    def get_or_create_card_wallet(session: Session, *, tenant_id: int, card_id: int) -> Wallet:
        wallet = session.exec(
            select(Wallet).where(
                Wallet.tenant_id == tenant_id,
                Wallet.owner_type == "card",
                Wallet.owner_card_id == card_id,
                Wallet.activo == True,
            )
        ).first()
        if wallet:
            return wallet

        wallet = Wallet(tenant_id=tenant_id, owner_type="card", owner_card_id=card_id, balance=Decimal("0.00"), activo=True)
        session.add(wallet)
        session.commit()
        session.refresh(wallet)
        return wallet

    @staticmethod
    def debit(
        session: Session,
        *,
        wallet_id: int,
        amount: Decimal,
        reference_type: Optional[str],
        reference_id: Optional[str],
        idempotency_key: Optional[str],
        created_by: Optional[int],
    ) -> WalletTxn:
        amount_q = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount_q <= 0:
            raise ValueError("INVALID_AMOUNT")

        if idempotency_key:
            existing = session.exec(
                select(WalletTxn).where(
                    WalletTxn.wallet_id == wallet_id,
                    WalletTxn.idempotency_key == idempotency_key,
                    WalletTxn.direction == "debit",
                )
            ).first()
            if existing:
                return existing

        wallet = session.get(Wallet, wallet_id)
        if not wallet or not wallet.activo:
            raise ValueError("WALLET_NOT_FOUND")

        if Decimal(str(wallet.balance)) < amount_q:
            raise ValueError("INSUFFICIENT_FUNDS")

        before = Decimal(str(wallet.balance))
        after = (before - amount_q).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        wallet.balance = after
        session.add(wallet)

        txn = WalletTxn(
            wallet_id=wallet.id,
            direction="debit",
            amount=amount_q,
            balance_before=before,
            balance_after=after,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
        session.add(txn)
        session.flush()
        return txn

    @staticmethod
    def credit(
        session: Session,
        *,
        wallet_id: int,
        amount: Decimal,
        reference_type: Optional[str],
        reference_id: Optional[str],
        idempotency_key: Optional[str],
        created_by: Optional[int],
    ) -> WalletTxn:
        amount_q = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount_q <= 0:
            raise ValueError("INVALID_AMOUNT")

        if idempotency_key:
            existing = session.exec(
                select(WalletTxn).where(
                    WalletTxn.wallet_id == wallet_id,
                    WalletTxn.idempotency_key == idempotency_key,
                    WalletTxn.direction == "credit",
                )
            ).first()
            if existing:
                return existing

        wallet = session.get(Wallet, wallet_id)
        if not wallet or not wallet.activo:
            raise ValueError("WALLET_NOT_FOUND")

        before = Decimal(str(wallet.balance))
        after = (before + amount_q).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        wallet.balance = after
        session.add(wallet)

        txn = WalletTxn(
            wallet_id=wallet.id,
            direction="credit",
            amount=amount_q,
            balance_before=before,
            balance_after=after,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
        session.add(txn)
        session.flush()
        return txn

