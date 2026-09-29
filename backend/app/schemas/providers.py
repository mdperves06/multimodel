from typing import Any

from pydantic import BaseModel, ConfigDict


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    capabilities: list[str]
    models: list[dict[str, Any]]
    supports_usage_api: bool
