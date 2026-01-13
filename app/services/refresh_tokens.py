import hashlib
import hmac
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.core.config import settings
from app.models.refresh_token import RefreshToken


def compute_refresh_token_hash(refresh_token: str) -> str:
    secret = settings.secret_key.encode("utf-8")
    message = refresh_token.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def get_refresh_token_by_hash(session: Session, token_hash: str) -> Optional[RefreshToken]:
    statement = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    return session.exec(statement).first()


def store_refresh_token(
    session: Session,
    *,
    user_id: int,
    refresh_token: str,
    jti: str,
    expires_at: datetime,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> RefreshToken:
    token_hash = compute_refresh_token_hash(refresh_token)
    record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        jti=jti,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def revoke_refresh_token(
    session: Session,
    record: RefreshToken,
    *,
    replaced_by_refresh_token: Optional[str] = None,
) -> RefreshToken:
    record.revoked_at = datetime.utcnow()
    if replaced_by_refresh_token:
        record.replaced_by_token_hash = compute_refresh_token_hash(replaced_by_refresh_token)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
