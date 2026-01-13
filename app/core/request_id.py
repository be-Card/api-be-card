import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

