from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.config import get_settings

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if not request.url.path.startswith(_DOC_PATHS):
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if request.url.path.startswith("/api"):
        h.setdefault("Cache-Control", "no-store")
    if get_settings().is_production:
        h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    return response
