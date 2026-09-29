import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AccountStatus, ConnectedAccount, Provider, User
from app.models.base import utcnow
from app.providers.registry import UnknownProviderError, get_adapter
from app.schemas.accounts import AccountCreate, AccountOut, AccountTestResult
from app.security.deps import get_current_user
from app.services import accounts as svc
from app.services.audit import audit

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _apply_validation(account: ConnectedAccount) -> tuple[bool, str]:
    adapter = get_adapter(account.provider.slug)
    result = adapter.validate_credentials(svc.load_credentials(account))
    now = utcnow()
    account.last_validated_at = now
    if result.limits:
        account.limits = result.limits
        account.limits_updated_at = now
    if result.valid:
        if account.status == AccountStatus.INVALID.value:
            account.status = AccountStatus.ACTIVE.value
        account.last_error = None
        account.last_error_at = None
        return True, "Connection successful"
    message = result.error or "Credential validation failed"
    account.status = AccountStatus.INVALID.value
    svc.record_error(account, message)
    return False, message


@router.get("", response_model=list[AccountOut])
def list_accounts(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AccountOut]:
    rows = db.scalars(
        select(ConnectedAccount)
        .where(ConnectedAccount.user_id == user.id)
        .order_by(ConnectedAccount.created_at)
    )
    return [svc.to_out(a) for a in rows]


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountOut:
    provider = db.scalar(
        select(Provider).where(Provider.slug == body.provider, Provider.is_enabled.is_(True))
    )
    if provider is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or unsupported provider")
    count = db.scalar(select(func.count()).where(ConnectedAccount.user_id == user.id)) or 0
    if count >= svc.MAX_ACCOUNTS_PER_USER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Connected account limit reached")

    api_key = body.api_key.get_secret_value().strip()
    credentials = svc.make_credentials(api_key)
    try:
        result = get_adapter(provider.slug).validate_credentials(credentials)
    except UnknownProviderError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Unknown or unsupported provider"
        ) from None
    if not result.valid:
        audit(
            db,
            "account.connect_failed",
            user_id=user.id,
            request=request,
            meta={"provider": provider.slug},
        )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, result.error or "Credentials were rejected"
        )

    now = utcnow()
    account = ConnectedAccount(
        user_id=user.id,
        provider_id=provider.id,
        label=body.label,
        encrypted_credentials=svc.encrypt_credentials(credentials),
        credential_hint=api_key[-4:],
        status=AccountStatus.ACTIVE.value,
        last_validated_at=now,
        limits=result.limits,
        limits_updated_at=now if result.limits else None,
    )
    db.add(account)
    db.commit()
    audit(
        db,
        "account.connect",
        user_id=user.id,
        request=request,
        target_type="account",
        target_id=account.id,
        meta={"provider": provider.slug, "label": account.label},
    )
    return svc.to_out(account)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AccountOut:
    return svc.to_out(svc.get_owned_account(db, user.id, account_id))


@router.post("/{account_id}/test", response_model=AccountTestResult)
def test_account(
    account_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccountTestResult:
    account = svc.get_owned_account(db, user.id, account_id)
    ok, message = _apply_validation(account)
    db.commit()
    audit(
        db,
        "account.test",
        user_id=user.id,
        request=request,
        target_type="account",
        target_id=account.id,
        meta={"ok": ok},
    )
    return AccountTestResult(ok=ok, message=message, account=svc.to_out(account))


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    account = svc.get_owned_account(db, user.id, account_id)
    label, provider = account.label, account.provider.slug
    db.delete(account)
    db.commit()
    audit(
        db,
        "account.disconnect",
        user_id=user.id,
        request=request,
        target_type="account",
        target_id=account_id,
        meta={"provider": provider, "label": label},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
