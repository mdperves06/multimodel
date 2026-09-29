from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

MAX_BODY_BYTES = 1_000_000  # API payloads are small JSON documents


async def body_limit_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    length = request.headers.get("content-length")
    if length is not None:
        try:
            too_big = int(length) > MAX_BODY_BYTES
        except ValueError:
            too_big = True
        if too_big:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
    return await call_next(request)
