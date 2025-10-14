from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import logging
from app.core.config import settings

# Configurar logging
logger = logging.getLogger(__name__)

# Configuración JWT
ALGORITHM = "HS256"


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
    """Verificar contraseña plana contra hash usando bcrypt directamente"""
    try:
        # Truncar contraseña de forma segura a bytes
        safe_password_bytes = _truncate_password_safely(plain_password)
        
        # Convertir hash a bytes si es string
        if isinstance(hashed_password, str):
            hashed_password_bytes = hashed_password.encode('utf-8')
        
        # Verificar usando bcrypt directamente
        return bcrypt.checkpw(safe_password_bytes, hashed_password_bytes)
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
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verificar y decodificar token JWT"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_refresh_token(data: dict) -> str:
    """Crear token de refresh"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt