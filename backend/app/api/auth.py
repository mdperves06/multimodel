import contextlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserOut
from app.security.deps import extract_token, get_current_user
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, decode_token, revoke_token
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, token: str, max_age: int) -> None:
    s = get_settings()
    response.set_cookie(
        s.cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=s.is_production,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    email = body.email.lower()
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists"
        ) from None
    token, ttl = create_access_token(user.id)
    _set_cookie(response, token, ttl)
    audit(db, "auth.register", user_id=user.id, request=request)
    return LoginResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else None)
    if user is None or not ok or not user.is_active:
        audit(db, "auth.login_failed", user_id=user.id if user else None, request=request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token, ttl = create_access_token(user.id)
    _set_cookie(response, token, ttl)
    audit(db, "auth.login", user_id=user.id, request=request)
    return LoginResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """Always clears the cookie, even if the session is already expired or revoked."""
    token = extract_token(request)
    if token:
        payload = decode_token(token)
        revoke_token(token)
        if payload is not None:
            with contextlib.suppress(ValueError):
                audit(db, "auth.logout", user_id=uuid.UUID(payload["sub"]), request=request)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(get_settings().cookie_name, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
