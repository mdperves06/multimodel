import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobCreate(BaseModel):
    type: Literal["image_generation"] = "image_generation"
    prompt: str = Field(min_length=1, max_length=4000)
    number_of_outputs: int = Field(default=1, ge=1, le=10)
    provider: str = Field(default="auto", max_length=50, pattern=r"^[a-z0-9_-]+$")
    model: str = Field(default="auto", max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    size: str | None = Field(default=None, max_length=20, pattern=r"^(auto|\d{2,4}x\d{2,4})$")
    quality: str | None = Field(default=None, max_length=20, pattern=r"^[a-z]+$")

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Prompt must not be blank")
        return v


class JobCreated(BaseModel):
    job_id: uuid.UUID
    status: str


class OutputOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    url: str
    mime_type: str
    size_bytes: int
    metadata: dict[str, Any]
    created_at: datetime


class GalleryItem(OutputOut):
    prompt: str
    provider: str | None
    model: str | None
    account_label: str | None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    prompt: str
    requested_provider: str
    requested_model: str
    provider_used: str | None
    model_used: str | None
    account_label: str | None
    number_of_outputs: int
    status: str
    attempts: int
    error: str | None
    events: list[dict[str, Any]]
    next_retry_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    outputs: list[OutputOut]


class Page[T](BaseModel):
    items: list[T]
    total: int


class OutputIds(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class DeleteResult(BaseModel):
    deleted: int


class UsageProviderInfo(BaseModel):
    available: bool
    message: str | None = None
    data: dict[str, Any] = {}


class AccountUsage(BaseModel):
    account_id: uuid.UUID
    label: str
    provider: str
    provider_name: str
    requests: int
    images: int
    input_tokens: int | None
    output_tokens: int | None
    last_request_at: datetime | None
    provider_usage: UsageProviderInfo
    rate_limits: dict[str, Any] | None
    rate_limits_updated_at: datetime | None


class DailyUsage(BaseModel):
    date: str
    requests: int
    images: int


class UsageSummary(BaseModel):
    requests: int
    images: int
    input_tokens: int | None
    output_tokens: int | None
    accounts: list[AccountUsage]
    daily: list[DailyUsage]
