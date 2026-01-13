from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Optional, Tuple

from sqlmodel import Session, select

from app.models.email_verification_token import EmailVerificationToken
from app.models.user_extended import Usuario


def compute_email_verification_token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class EmailVerificationService:
    @staticmethod
    def create_token(
        session: Session,
        user: Usuario,
        expires_in_minutes: int = 60 * 24,
    ) -> Tuple[str, datetime]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = compute_email_verification_token_hash(raw_token)
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

        record = EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(record)
        session.commit()
        return raw_token, expires_at

    @staticmethod
    def find_valid_token(session: Session, raw_token: str) -> Optional[EmailVerificationToken]:
        token_hash = compute_email_verification_token_hash(raw_token)
        record = session.exec(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)).first()
        if not record:
            return None
        if record.used_at is not None:
            return None
        if record.expires_at <= datetime.utcnow():
            return None
        return record

    @staticmethod
    def verify_email(session: Session, raw_token: str) -> Usuario:
        record = EmailVerificationService.find_valid_token(session, raw_token)
        if not record:
            raise ValueError("Token inválido o expirado")

        user = session.get(Usuario, record.user_id)
        if not user:
            raise ValueError("Usuario no encontrado")

        user.verificado = True
        record.used_at = datetime.utcnow()

        session.add(user)
        session.add(record)
        session.commit()
        session.refresh(user)
        return user

