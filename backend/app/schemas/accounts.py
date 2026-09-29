import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, SecretStr, field_validator


class AccountCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=100)
    api_key: SecretStr = Field(min_length=8, max_length=500)

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Label must not be blank")
        return v


class AccountOut(BaseModel):
    """Never includes credentials. `credential_hint` is only the last few characters."""

    id: uuid.UUID
    provider: str
    provider_name: str
    label: str
    status: str
    available: bool
    capabilities: list[str]
    models: list[dict[str, Any]]
    credential_hint: str
    rate_limited_until: datetime | None
    last_request_at: datetime | None
    last_validated_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None
    limits: dict[str, Any] | None
    created_at: datetime


class AccountTestResult(BaseModel):
    ok: bool
    message: str
    account: AccountOut
