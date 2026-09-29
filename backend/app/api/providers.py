from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Provider, User
from app.schemas.providers import ProviderOut
from app.security.deps import get_current_user

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
def list_providers(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Provider]:
    return list(
        db.scalars(select(Provider).where(Provider.is_enabled.is_(True)).order_by(Provider.name))
    )
