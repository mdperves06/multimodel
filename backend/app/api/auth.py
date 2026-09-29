import contextlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserOut,
)
from app.security.deps import extract_token, get_current_user
from app.security.passwords import hash_password, verify_password
from app.security.ratelimit import hit
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
    token, ttl = create_access_token(user.id, user.token_version)
    _set_cookie(response, token, ttl)
    audit(db, "auth.register", user_id=user.id, request=request)
    return LoginResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    email = body.email.lower()
    if get_settings().rate_limit_enabled:
        allowed, retry_after = hit(
            f"login-email:{email}", get_settings().auth_rate_limit_per_minute
        )
        if not allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many attempts for this account. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(body.password, user.password_hash if user else None)
    if user is None or not ok or not user.is_active:
        audit(db, "auth.login_failed", user_id=user.id if user else None, request=request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token, ttl = create_access_token(user.id, user.token_version)
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
            with contextlib.suppress(ValueError, SQLAlchemyError):
                user_id = uuid.UUID(payload["sub"])
                if db.get(User, user_id) is not None:  # a deleted user has nothing to audit
                    audit(db, "auth.logout", user_id=user_id, request=request)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(get_settings().cookie_name, path="/")
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Invalidate every session for this user, on all devices."""
    user.token_version += 1
    db.commit()
    audit(db, "auth.logout_all", user_id=user.id, request=request)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(get_settings().cookie_name, path="/")
    return response


@router.post("/change-password", response_model=LoginResponse)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Verify the current password, set a new one, sign out every other session."""
    allowed, retry_after = hit(f"chpw:{user.id}", 5)
    if not allowed and get_settings().rate_limit_enabled:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
    if not verify_password(body.current_password, user.password_hash):
        audit(db, "auth.change_password_failed", user_id=user.id, request=request)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    token, ttl = create_access_token(user.id, user.token_version)
    _set_cookie(response, token, ttl)
    audit(db, "auth.change_password", user_id=user.id, request=request)
    return LoginResponse(user=UserOut.model_validate(user), access_token=token)
