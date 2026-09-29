from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings

_SAFE = {"GET", "HEAD", "OPTIONS"}


async def origin_check_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject cross-site state-changing browser requests (defence in depth on top of SameSite)."""
    if request.method not in _SAFE:
        origin = request.headers.get("origin")
        if origin and origin not in get_settings().cors_origin_list:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    return await call_next(request)
