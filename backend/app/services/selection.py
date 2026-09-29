"""Provider/account selection for "auto" jobs.

An account is eligible only if it: belongs to the user, targets a registered provider that
supports the capability (and requested model), has valid credentials, is not inside a
provider-imposed rate-limit window, and does not report zero remaining request capacity.
We never try to get around a limit: if nothing is available we wait for the provider's window.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountStatus, ConnectedAccount
from app.models.base import utcnow
from app.providers.base import IMAGE_GENERATION
from app.providers.registry import get_registry

NO_ACCOUNTS = "no_accounts"
UNSUPPORTED_MODEL = "unsupported_model"
RATE_LIMITED = "rate_limited"
NO_VALID_CREDENTIALS = "no_valid_credentials"


@dataclass
class Selection:
    account: ConnectedAccount | None = None
    model: str | None = None
    reason: str | None = None
    retry_at: datetime | None = None


def _limit_window_end(account: ConnectedAccount) -> datetime | None:
    """If the provider last reported 0 remaining requests, when does that window reset?"""
    limits = account.limits or {}
    if limits.get("remaining_requests") == 0 and account.limits_updated_at:
        reset = limits.get("reset_requests_seconds")
        if isinstance(reset, int | float):
            return account.limits_updated_at + timedelta(seconds=float(reset))
    return None


def select_account(
    db: Session,
    user_id: uuid.UUID,
    provider: str = "auto",
    model: str = "auto",
    capability: str = IMAGE_GENERATION,
    exclude: Collection[uuid.UUID] = (),
) -> Selection:
    registry = get_registry()
    now = utcnow()
    accounts = [
        a
        for a in db.scalars(select(ConnectedAccount).where(ConnectedAccount.user_id == user_id))
        if a.id not in exclude and (provider == "auto" or a.provider.slug == provider)
    ]
    capable = [a for a in accounts if a.provider.slug in registry]
    if not capable:
        return Selection(reason=NO_ACCOUNTS)

    wanted = None if model == "auto" else model
    compatible = [a for a in capable if registry[a.provider.slug].supports(capability, wanted)]
    if not compatible:
        return Selection(reason=UNSUPPORTED_MODEL if wanted else NO_ACCOUNTS)

    valid = [a for a in compatible if a.status == AccountStatus.ACTIVE.value]
    if not valid:
        return Selection(reason=NO_VALID_CREDENTIALS)

    available: list[ConnectedAccount] = []
    waits: list[datetime] = []
    for account in valid:
        blocked_until = max(
            (t for t in (account.rate_limited_until, _limit_window_end(account)) if t),
            default=None,
        )
        if blocked_until and blocked_until > now:
            waits.append(blocked_until)
        else:
            available.append(account)
    if not available:
        return Selection(reason=RATE_LIMITED, retry_at=min(waits))

    # Least recently used first spreads load across accounts.
    available.sort(key=lambda a: (a.last_request_at is not None, a.last_request_at or a.created_at))
    chosen = available[0]
    resolved = wanted or registry[chosen.provider.slug].default_model(capability)
    return Selection(account=chosen, model=resolved)
