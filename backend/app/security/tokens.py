import uuid
from datetime import timedelta
from typing import Any

import jwt

from app.config import get_settings
from app.models.base import utcnow
from app.redis_client import get_redis

ALGORITHM = "HS256"


def create_access_token(user_id: uuid.UUID, token_version: int = 0) -> tuple[str, int]:
    s = get_settings()
    now = utcnow()
    ttl = timedelta(minutes=s.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "jti": uuid.uuid4().hex,
        "tv": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub", "jti"]},
        )
    except jwt.PyJWTError:
        return None
    try:
        if get_redis().exists(f"revoked:{payload['jti']}"):
            return None
    except Exception:  # noqa: BLE001 - if Redis is down, fail closed for safety
        return None
    return payload


def revoke_token(token: str) -> None:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError:
        return
    remaining = max(int(payload.get("exp", 0)) - int(utcnow().timestamp()), 1)
    get_redis().setex(f"revoked:{payload['jti']}", remaining, "1")
