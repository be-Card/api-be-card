import logging

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import request_id_ctx


logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    header_request_id = request.headers.get("X-Request-ID")
    if header_request_id:
        return header_request_id
    ctx_request_id = request_id_ctx.get()
    return ctx_request_id or ""


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": "HTTP_EXCEPTION",
            "request_id": _get_request_id(request),
        },
    )


def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": "HTTP_EXCEPTION",
            "request_id": _get_request_id(request),
        },
    )


def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": jsonable_encoder(exc.errors()),
            "code": "VALIDATION_ERROR",
            "request_id": _get_request_id(request),
        },
    )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Demasiadas solicitudes",
            "code": "RATE_LIMIT_EXCEEDED",
            "request_id": _get_request_id(request),
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", ""))} if getattr(exc, "retry_after", None) else None,
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", extra={"request_id": _get_request_id(request)})
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "code": "INTERNAL_ERROR",
            "request_id": _get_request_id(request),
        },
    )
