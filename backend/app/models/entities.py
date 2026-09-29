import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime, new_id, utcnow


class AccountStatus(enum.StrEnum):
    ACTIVE = "active"
    INVALID = "invalid"  # provider rejected the credentials
    DISABLED = "disabled"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_JOB_STATUSES = (JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.RETRYING)
TERMINAL_JOB_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    accounts: Mapped[list["ConnectedAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    models: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    supports_usage_api: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    credential_hint: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(20), default=AccountStatus.ACTIVE.value)
    rate_limited_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_request_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    limits: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    limits_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="accounts")
    provider: Mapped[Provider] = relationship(lazy="joined")
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connected_accounts.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(50), default="image_generation")
    prompt: Mapped[str] = mapped_column(Text)
    requested_provider: Mapped[str] = mapped_column(String(50), default="auto")
    requested_model: Mapped[str] = mapped_column(String(100), default="auto")
    provider_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    number_of_outputs: Mapped[int] = mapped_column(Integer, default=1)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.QUEUED.value, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    next_retry_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="jobs")
    outputs: Mapped[list["JobOutput"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobOutput.created_at"
    )


class JobOutput(Base):
    __tablename__ = "job_outputs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100), default="image/png")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    job: Mapped[Job] = relationship(back_populates="outputs")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_accounts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    requests: Mapped[int] = mapped_column(Integer, default=1)
    images: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    account: Mapped[ConnectedAccount] = relationship(back_populates="usage_records")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
