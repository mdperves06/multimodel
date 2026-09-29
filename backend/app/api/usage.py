import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.jobs import UsageSummary
from app.security.deps import get_current_user
from app.services import accounts as accounts_svc
from app.services import usage as svc

router = APIRouter(tags=["usage"])


@router.get("/usage", response_model=UsageSummary)
def usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UsageSummary:
    return svc.summarize(db, user.id)


@router.get("/accounts/{account_id}/usage", response_model=UsageSummary)
def account_usage(
    account_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UsageSummary:
    accounts_svc.get_owned_account(db, user.id, account_id)
    return svc.summarize(db, user.id, account_id)
