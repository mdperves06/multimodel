from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Provider
from app.providers.registry import get_registry


def sync_providers(db: Session) -> None:
    """Upsert Provider rows from the adapter registry; disable rows with no adapter."""
    registry = get_registry()
    existing = {p.slug: p for p in db.scalars(select(Provider))}
    for slug, adapter in registry.items():
        row = existing.get(slug) or Provider(slug=slug, name=adapter.name)
        row.name = adapter.name
        row.capabilities = list(adapter.capabilities)
        row.models = [m.to_dict() for m in adapter.models]
        row.supports_usage_api = adapter.supports_usage_api
        row.is_enabled = True
        db.add(row)
    for slug, row in existing.items():
        if slug not in registry:
            row.is_enabled = False
    db.commit()
