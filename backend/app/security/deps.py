import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.security.tokens import decode_token

_UNAUTHORIZED = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(get_settings().cookie_name)


def get_token(request: Request) -> str:
    token = extract_token(request)
    if not token:
        raise _UNAUTHORIZED
    return token


def get_current_user(token: str = Depends(get_token), db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    if payload is None:
        raise _UNAUTHORIZED
    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError) as exc:
        raise _UNAUTHORIZED from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active or payload.get("tv", 0) != user.token_version:
        raise _UNAUTHORIZED
    return user
