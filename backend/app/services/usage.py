"""Usage reporting.

Two clearly separated sources:
  * counts recorded by this app for requests it sent (requests, images, tokens if the provider
    returned them) - these are real, not estimates;
  * provider-reported usage / rate limits - shown only when the provider exposes them.
Nothing is invented: unknown values are None and unsupported providers say so.
"""

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ConnectedAccount, UsageRecord
from app.models.base import utcnow
from app.providers.base import UNAVAILABLE_USAGE_MESSAGE
from app.schemas.jobs import AccountUsage, DailyUsage, UsageProviderInfo, UsageSummary

DAYS = 14


def _account_usage(db: Session, account: ConnectedAccount) -> AccountUsage:
    row = db.execute(
        select(
            func.coalesce(func.sum(UsageRecord.requests), 0),
            func.coalesce(func.sum(UsageRecord.images), 0),
            func.sum(UsageRecord.input_tokens),
            func.sum(UsageRecord.output_tokens),
        ).where(UsageRecord.account_id == account.id)
    ).one()
    provider = account.provider
    # No adapter currently exposes provider-side usage; the message is shown instead of numbers.
    info = UsageProviderInfo(available=False, message=UNAVAILABLE_USAGE_MESSAGE)
    return AccountUsage(
        account_id=account.id,
        label=account.label,
        provider=provider.slug,
        provider_name=provider.name,
        requests=int(row[0]),
        images=int(row[1]),
        input_tokens=int(row[2]) if row[2] is not None else None,
        output_tokens=int(row[3]) if row[3] is not None else None,
        last_request_at=account.last_request_at,
        provider_usage=info,
        rate_limits=account.limits,
        rate_limits_updated_at=account.limits_updated_at,
    )


def summarize(db: Session, user_id: uuid.UUID, account_id: uuid.UUID | None = None) -> UsageSummary:
    query = select(ConnectedAccount).where(ConnectedAccount.user_id == user_id)
    if account_id:
        query = query.where(ConnectedAccount.id == account_id)
    accounts = [
        _account_usage(db, a) for a in db.scalars(query.order_by(ConnectedAccount.created_at))
    ]

    since = utcnow() - timedelta(days=DAYS - 1)
    recent = select(UsageRecord).where(
        UsageRecord.user_id == user_id, UsageRecord.created_at >= since
    )
    if account_id:
        recent = recent.where(UsageRecord.account_id == account_id)
    per_day: dict[str, DailyUsage] = {}
    for i in range(DAYS):
        day = (since + timedelta(days=i)).date().isoformat()
        per_day[day] = DailyUsage(date=day, requests=0, images=0)
    for rec in db.scalars(recent):
        day = rec.created_at.date().isoformat()
        if day in per_day:
            per_day[day].requests += rec.requests
            per_day[day].images += rec.images

    def tokens(attr: str) -> int | None:
        values = [getattr(a, attr) for a in accounts if getattr(a, attr) is not None]
        return sum(values) if values else None

    return UsageSummary(
        requests=sum(a.requests for a in accounts),
        images=sum(a.images for a in accounts),
        input_tokens=tokens("input_tokens"),
        output_tokens=tokens("output_tokens"),
        accounts=accounts,
        daily=list(per_day.values()),
    )
