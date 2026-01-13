"""
Rate limiting configuration for the API
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

# Create limiter instance
limiter = Limiter(key_func=get_remote_address)

# Rate limit decorators for different endpoints

# Strict rate limiting for authentication endpoints
AUTH_RATE_LIMIT = "5/minute"  # 5 requests per minute for login/register

# Moderate rate limiting for write operations
WRITE_RATE_LIMIT = "30/minute"  # 30 requests per minute for POST/PUT/DELETE

# Permissive rate limiting for read operations
READ_RATE_LIMIT = "100/minute"  # 100 requests per minute for GET

# Very strict for password-related operations
PASSWORD_RATE_LIMIT = "3/minute"  # Only 3 attempts per minute


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, checking for proxy headers first
    """
    # Check common proxy headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs, take the first
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct connection
    if request.client:
        return request.client.host

    return "unknown"
