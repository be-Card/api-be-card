from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4
from jose import JWTError, jwt
import bcrypt
import logging
from app.core.config import settings

# Configurar logging
logger = logging.getLogger(__name__)

def _truncate_password_safely(password: str) -> bytes:
    """
    Truncar contraseña de forma segura a 72 bytes para bcrypt.
    Retorna bytes directamente para evitar problemas de codificación.
    """
    try:
        password_bytes = password.encode('utf-8')
        if len(password_bytes) <= 72:
            return password_bytes
        
        return password_bytes[:72]
    except Exception as e:
        logger.warning(f"Error al truncar contraseña: {e}")
        return password[:72].encode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña plana contra hash.
    Soporta hashes bcrypt (preferido) y fallback legado sha256 (semillas antiguas).
    """
    try:
        # Verificación con bcrypt si el hash tiene formato bcrypt
        if isinstance(hashed_password, str) and hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
            safe_password_bytes = _truncate_password_safely(plain_password)
            return bcrypt.checkpw(safe_password_bytes, hashed_password.encode('utf-8'))
        
        # Fallback legado: hash sha256 hexadecimal de 64 caracteres
        import re, hashlib
        if isinstance(hashed_password, str) and re.fullmatch(r"[0-9a-fA-F]{64}", hashed_password):
            return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password
        
        return False
    except Exception as e:
        logger.error(f"Error al verificar contraseña: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Generar hash de contraseña usando bcrypt directamente"""
    try:
        # Truncar contraseña de forma segura a bytes
        safe_password_bytes = _truncate_password_safely(password)
        
        # Generar salt y hash usando bcrypt directamente
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(safe_password_bytes, salt)
        
        # Retornar como string
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error al generar hash de contraseña: {e}")
        raise ValueError(f"No se pudo generar hash de contraseña: {str(e)}")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crear token JWT de acceso"""
    to_encode = data.copy()
    now = datetime.utcnow()
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "nbf": now,
            "type": "access",
            "jti": str(uuid4()),
        }
    )
    if settings.jwt_issuer:
        to_encode["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        to_encode["aud"] = settings.jwt_audience
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str, expected_type: Optional[str] = None) -> Optional[dict]:
    """Verificar y decodificar token JWT"""
    try:
        decode_kwargs = {}
        if settings.jwt_issuer:
            decode_kwargs["issuer"] = settings.jwt_issuer
        if settings.jwt_audience:
            decode_kwargs["audience"] = settings.jwt_audience

        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm], **decode_kwargs)
        token_type = payload.get("type") or "access"
        payload["type"] = token_type
        if expected_type and token_type != expected_type:
            return None
        return payload
    except JWTError:
        return None


def create_refresh_token(data: dict) -> tuple[str, str, datetime]:
    """Crear token de refresh"""
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid4())
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "nbf": now,
            "type": "refresh",
            "jti": jti,
        }
    )
    if settings.jwt_issuer:
        to_encode["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        to_encode["aud"] = settings.jwt_audience
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt, jti, expire
