import logging
import threading
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_memory: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

_AUTH_PATHS = ("/api/auth/login", "/api/auth/register")


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def hit(key: str, limit: int, window: int = 60) -> tuple[bool, int]:
    """Fixed-window counter. Returns (allowed, retry_after_seconds)."""
    now = int(time.time())
    bucket = now // window
    retry_after = window - (now % window)
    try:
        r = get_redis()
        rkey = f"rl:{key}:{bucket}"
        count = int(r.incr(rkey))
        if count == 1:
            r.expire(rkey, window + 1)
        return count <= limit, retry_after
    except Exception:  # Redis unavailable: fall back to per-process limiting
        logger.warning("rate limiter falling back to in-memory counters")
        with _lock:
            b, c = _memory[key]
            c = c + 1 if b == bucket else 1
            _memory[key] = (bucket, c)
            return c <= limit, retry_after


def reset_memory() -> None:
    with _lock:
        _memory.clear()


async def rate_limit_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    s = get_settings()
    path = request.url.path
    if s.rate_limit_enabled and path.startswith("/api") and path != "/api/health":
        ip = client_ip(request)
        checks = [(f"g:{ip}", s.global_rate_limit_per_minute)]
        if path in _AUTH_PATHS:
            checks.append((f"a:{ip}:{path}", s.auth_rate_limit_per_minute))
        for key, limit in checks:
            allowed, retry_after = hit(key, limit)
            if not allowed:
                return JSONResponse(
                    {"detail": "Too many requests. Please slow down."},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
    return await call_next(request)
