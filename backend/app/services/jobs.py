import logging
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ACTIVE_JOB_STATUSES, Job, JobOutput, JobStatus, User
from app.models.base import utcnow
from app.providers.registry import get_registry
from app.schemas.jobs import GalleryItem, JobCreate, JobOut, OutputOut
from app.workers.queue import JobQueue

logger = logging.getLogger(__name__)

# Timeline stages shown in the UI, in order.
STAGES = ("created", "queued", "processing", "generating", "storing", "completed")


def add_event(job: Job, stage: str, message: str | None = None) -> None:
    event: dict[str, Any] = {"stage": stage, "at": utcnow().isoformat()}
    if message:
        event["message"] = message
    job.events = [*job.events, event]  # reassign so the JSON column is flagged as changed


def output_to_out(output: JobOutput) -> OutputOut:
    return OutputOut(
        id=output.id,
        job_id=output.job_id,
        url=f"/api/outputs/{output.id}/file",
        mime_type=output.mime_type,
        size_bytes=output.size_bytes,
        metadata=output.meta,
        created_at=output.created_at,
    )


def job_to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        type=job.type,
        prompt=job.prompt,
        requested_provider=job.requested_provider,
        requested_model=job.requested_model,
        provider_used=job.provider_used,
        model_used=job.model_used,
        account_label=job.account_label,
        number_of_outputs=job.number_of_outputs,
        status=job.status,
        attempts=job.attempts,
        error=job.error,
        events=job.events,
        next_retry_at=job.next_retry_at,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        outputs=[output_to_out(o) for o in job.outputs],
    )


def gallery_item(output: JobOutput) -> GalleryItem:
    base = output_to_out(output)
    job = output.job
    return GalleryItem(
        **base.model_dump(),
        prompt=job.prompt,
        provider=job.provider_used,
        model=job.model_used,
        account_label=job.account_label,
    )


def get_owned_job(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def _validate_targets(payload: JobCreate) -> None:
    registry = get_registry()
    if payload.provider != "auto":
        adapter = registry.get(payload.provider)
        if adapter is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown provider")
        if not adapter.supports(payload.type):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provider does not support this task")
        adapters = [adapter]
    else:
        adapters = [a for a in registry.values() if a.supports(payload.type)]
    if payload.model != "auto" and not any(
        a.supports(payload.type, payload.model) for a in adapters
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Model is not supported by the provider")


def create_job(db: Session, user: User, payload: JobCreate, queue: JobQueue) -> Job:
    settings = get_settings()
    if payload.number_of_outputs > settings.max_outputs_per_job:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"At most {settings.max_outputs_per_job} outputs per job",
        )
    _validate_targets(payload)
    active = db.scalar(
        select(func.count()).where(
            Job.user_id == user.id, Job.status.in_([s.value for s in ACTIVE_JOB_STATUSES])
        )
    )
    if (active or 0) >= settings.max_active_jobs_per_user:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many active jobs. Wait for some to finish."
        )

    job = Job(
        user_id=user.id,
        type=payload.type,
        prompt=payload.prompt,
        requested_provider=payload.provider,
        requested_model=payload.model,
        number_of_outputs=payload.number_of_outputs,
        params={"size": payload.size, "quality": payload.quality},
        status=JobStatus.QUEUED.value,
        events=[],
    )
    add_event(job, "created")
    add_event(job, "queued")
    db.add(job)
    db.commit()
    try:
        queue.enqueue(job.id)
    except Exception:
        logger.exception("could not enqueue job %s", job.id)
        job.status = JobStatus.FAILED.value
        job.error = "Job queue is unavailable"
        job.completed_at = utcnow()
        add_event(job, "failed", job.error)
        db.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Job queue is unavailable"
        ) from None
    return job


def cancel_job(db: Session, job: Job) -> Job:
    if job.status not in {s.value for s in ACTIVE_JOB_STATUSES}:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot cancel a {job.status} job")
    job.status = JobStatus.CANCELLED.value
    job.completed_at = utcnow()
    job.next_retry_at = None
    add_event(job, "cancelled")
    db.commit()
    return job


def retry_job(db: Session, job: Job, queue: JobQueue) -> Job:
    if job.status not in (JobStatus.FAILED.value, JobStatus.CANCELLED.value):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only failed or cancelled jobs can be retried"
        )
    job.status = JobStatus.QUEUED.value
    job.error = None
    job.attempts = 0
    job.started_at = None
    job.completed_at = None
    job.next_retry_at = None
    add_event(job, "queued", "Retry requested")
    db.commit()
    queue.enqueue(job.id)
    return job
