import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.security.ratelimit import client_ip


def audit(
    db: Session,
    action: str,
    *,
    user_id: uuid.UUID | None,
    request: Request | None = None,
    target_type: str | None = None,
    target_id: object | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Record an audit event. Never pass secrets in `meta`."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip_address=client_ip(request) if request is not None else None,
            meta=meta or {},
        )
    )
    db.commit()
