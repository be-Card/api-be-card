from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Optional, Tuple

from sqlmodel import Session, select

from app.core.security import get_password_hash
from app.models.password_reset_token import PasswordResetToken
from app.models.user_extended import Usuario
from app.models.refresh_token import RefreshToken


def compute_password_reset_token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class PasswordResetService:
    @staticmethod
    def create_reset_token(
        session: Session,
        user: Usuario,
        expires_in_minutes: int = 30
    ) -> Tuple[str, datetime]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = compute_password_reset_token_hash(raw_token)
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

        record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(record)
        session.commit()
        return raw_token, expires_at

    @staticmethod
    def mark_used(session: Session, record: PasswordResetToken) -> None:
        record.used_at = datetime.utcnow()
        session.add(record)
        session.commit()

    @staticmethod
    def find_valid_token(session: Session, raw_token: str) -> Optional[PasswordResetToken]:
        token_hash = compute_password_reset_token_hash(raw_token)
        record = session.exec(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        ).first()
        if not record:
            return None
        if record.used_at is not None:
            return None
        if record.expires_at <= datetime.utcnow():
            return None
        return record

    @staticmethod
    def reset_password(session: Session, raw_token: str, new_password: str) -> None:
        if not new_password or len(new_password) > 72:
            raise ValueError("La contraseña no es válida")

        record = PasswordResetService.find_valid_token(session, raw_token)
        if not record:
            raise ValueError("Token inválido o expirado")

        user = session.get(Usuario, record.user_id)
        if not user:
            raise ValueError("Usuario no encontrado")

        user.password_hash = get_password_hash(new_password)
        user.password_salt = ""
        user.intentos_login_fallidos = 0
        user.bloqueado_hasta = None
        user.activo = True

        PasswordResetService.mark_used(session, record)

        tokens = session.exec(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
        now = datetime.utcnow()
        for t in tokens:
            if t.revoked_at is None:
                t.revoked_at = now
                session.add(t)

        session.add(user)
        session.commit()

