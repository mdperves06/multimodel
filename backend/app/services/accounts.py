import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountStatus, ConnectedAccount
from app.models.base import utcnow
from app.schemas.accounts import AccountOut
from app.security.crypto import decrypt_credentials
from app.security.crypto import encrypt_credentials as _encrypt

MAX_ACCOUNTS_PER_USER = 20


def is_available(account: ConnectedAccount, now: datetime | None = None) -> bool:
    now = now or utcnow()
    if account.status != AccountStatus.ACTIVE.value:
        return False
    return not (account.rate_limited_until and account.rate_limited_until > now)


def to_out(account: ConnectedAccount) -> AccountOut:
    provider = account.provider
    return AccountOut(
        id=account.id,
        provider=provider.slug,
        provider_name=provider.name,
        label=account.label,
        status=account.status,
        available=is_available(account),
        capabilities=list(provider.capabilities),
        models=list(provider.models),
        credential_hint=account.credential_hint,
        rate_limited_until=account.rate_limited_until,
        last_request_at=account.last_request_at,
        last_validated_at=account.last_validated_at,
        last_error=account.last_error,
        last_error_at=account.last_error_at,
        limits=account.limits,
        created_at=account.created_at,
    )


def get_owned_account(db: Session, user_id: uuid.UUID, account_id: uuid.UUID) -> ConnectedAccount:
    account = db.scalar(
        select(ConnectedAccount).where(
            ConnectedAccount.id == account_id, ConnectedAccount.user_id == user_id
        )
    )
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    return account


def make_credentials(api_key: str) -> dict[str, str]:
    return {"api_key": api_key}


def encrypt_credentials(credentials: dict[str, str]) -> str:
    return _encrypt(credentials)


def load_credentials(account: ConnectedAccount) -> dict[str, str]:
    return {k: str(v) for k, v in decrypt_credentials(account.encrypted_credentials).items()}


def record_error(account: ConnectedAccount, message: str) -> None:
    account.last_error = message[:500]
    account.last_error_at = utcnow()
