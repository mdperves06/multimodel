"""Runs a single job: choose an account, call the provider adapter, store results.

Retry policy
  * HTTP 429 / quota: mark that account as limited for exactly the provider-supplied window,
    then try another eligible account, otherwise wait for the earliest window to end.
  * Transient errors (timeouts, 5xx): exponential backoff.
  * Auth errors: the account is flagged invalid and another account is tried.
  * Request errors (bad params, policy): fail immediately, no retry.
  All retries are bounded by MAX_JOB_ATTEMPTS.
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import AccountStatus, ConnectedAccount, Job, JobOutput, JobStatus, UsageRecord
from app.models.base import utcnow
from app.providers.base import (
    IMAGE_GENERATION,
    ImageRequest,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTransientError,
)
from app.providers.registry import get_adapter
from app.services import selection
from app.services.accounts import load_credentials, record_error
from app.services.jobs import add_event
from app.services.storage import Storage, get_storage
from app.workers.queue import JobQueue

logger = logging.getLogger(__name__)

_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _fail(db: Session, job: Job, message: str) -> None:
    job.status = JobStatus.FAILED.value
    job.error = message[:1000]
    job.completed_at = utcnow()
    job.next_retry_at = None
    add_event(job, "failed", job.error)
    db.commit()


def _retry_later(db: Session, job: Job, queue: JobQueue, delay: float, reason: str) -> None:
    if job.attempts >= get_settings().max_job_attempts:
        _fail(db, job, f"{reason} (gave up after {job.attempts} attempts)")
        return
    delay = max(delay, 1.0)
    job.status = JobStatus.RETRYING.value
    job.next_retry_at = utcnow() + timedelta(seconds=delay)
    add_event(job, "retrying", f"{reason}. Retrying in {int(delay)}s")
    db.commit()
    queue.enqueue_delayed(job.id, delay)


def _is_cancelled(db: Session, job: Job) -> bool:
    db.refresh(job)
    return job.status == JobStatus.CANCELLED.value


def _claim(db: Session, job_id: uuid.UUID) -> Job | None:
    """Atomically move queued/retrying -> processing so only one worker runs the job."""
    claimed = db.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RETRYING.value]),
        )
        .values(status=JobStatus.PROCESSING.value, next_retry_at=None)
    ).rowcount  # type: ignore[attr-defined]
    db.commit()
    if not claimed:
        return None
    job = db.get(Job, job_id)
    if job is None:
        return None
    db.refresh(job)
    job.attempts += 1
    if job.started_at is None:
        job.started_at = utcnow()
    add_event(job, "processing")
    db.commit()
    return job


def process_job(
    job_id: uuid.UUID | str,
    session_factory: sessionmaker[Session],
    queue: JobQueue,
    storage: Storage | None = None,
) -> None:
    storage = storage or get_storage()
    jid = uuid.UUID(str(job_id))
    with session_factory() as db:
        job = _claim(db, jid)
        if job is None:
            return
        try:
            _run(db, job, queue, storage)
        except Exception:
            logger.exception("job %s crashed", jid)
            db.rollback()
            job = db.get(Job, jid)
            if job is not None and job.status == JobStatus.PROCESSING.value:
                _fail(db, job, "Internal error while processing the job")


def _run(db: Session, job: Job, queue: JobQueue, storage: Storage) -> None:
    if _is_cancelled(db, job):
        return
    remaining = job.number_of_outputs - len(job.outputs)
    if remaining <= 0:
        _complete(db, job)
        return

    choice = selection.select_account(
        db, job.user_id, job.requested_provider, job.requested_model, IMAGE_GENERATION
    )
    if choice.account is None or choice.model is None:
        _handle_no_account(db, job, queue, choice)
        return

    account, model_id = choice.account, choice.model
    adapter = get_adapter(account.provider.slug)
    model = adapter.get_model(model_id)
    if model is None:
        _fail(db, job, f"Model {model_id} is not available")
        return
    job.account_id = account.id
    job.provider_used = account.provider.slug
    job.account_label = account.label
    job.model_used = model_id
    add_event(job, "generating", f"{account.provider.name} / {model_id}")
    db.commit()

    try:
        credentials = load_credentials(account)
    except ValueError:
        account.status = AccountStatus.INVALID.value
        record_error(account, "Stored credentials could not be decrypted")
        _fail(db, job, "Stored credentials for the selected account could not be decrypted")
        return

    size = job.params.get("size")
    size = size if size in model.sizes else model.default_size
    quality = job.params.get("quality")
    quality = quality if quality in model.qualities else None

    storing_logged = False
    while remaining > 0:
        batch = min(remaining, model.max_outputs_per_request)
        try:
            result = adapter.generate_image(
                credentials, ImageRequest(job.prompt, batch, model_id, size, quality)
            )
        except ProviderError as exc:
            _handle_provider_error(db, job, queue, account, exc)
            return

        now = utcnow()
        account.last_request_at = now
        account.last_error = None
        account.last_error_at = None
        if result.limits:
            account.limits = result.limits
            account.limits_updated_at = now
        db.add(
            UsageRecord(
                account_id=account.id,
                user_id=job.user_id,
                job_id=job.id,
                requests=1,
                images=len(result.images),
                input_tokens=(result.usage or {}).get("input_tokens"),
                output_tokens=(result.usage or {}).get("output_tokens"),
            )
        )
        db.commit()

        if _is_cancelled(db, job):  # results of a cancelled job are discarded, not shown
            return
        if not storing_logged:
            add_event(job, "storing")
            db.commit()
            storing_logged = True
        for image in result.images[:remaining]:
            ext = _EXT.get(image.mime_type, "bin")
            key = f"{job.user_id}/{job.id}/{uuid.uuid4().hex}.{ext}"
            storage.put(key, image.data, image.mime_type)
            try:
                db.add(
                    JobOutput(
                        job_id=job.id,
                        user_id=job.user_id,
                        storage_key=key,
                        mime_type=image.mime_type,
                        size_bytes=len(image.data),
                        meta={**image.metadata, "model": model_id},
                    )
                )
                db.commit()
            except Exception:
                storage.delete(key)
                raise
            remaining -= 1
        db.refresh(job)
    _complete(db, job)


def _complete(db: Session, job: Job) -> None:
    job.status = JobStatus.COMPLETED.value
    job.completed_at = utcnow()
    job.error = None
    add_event(job, "completed")
    db.commit()


def _handle_no_account(db: Session, job: Job, queue: JobQueue, choice: selection.Selection) -> None:
    if choice.reason == selection.RATE_LIMITED and choice.retry_at is not None:
        wait = (choice.retry_at - utcnow()).total_seconds()
        _retry_later(db, job, queue, wait, "All matching accounts are rate limited")
        return
    messages = {
        selection.NO_ACCOUNTS: (
            "No connected account supports this request. Connect a provider first."
        ),
        selection.UNSUPPORTED_MODEL: (
            "None of your connected accounts support the requested model."
        ),
        selection.NO_VALID_CREDENTIALS: (
            "All matching accounts have invalid credentials. Re-test or reconnect them."
        ),
    }
    _fail(db, job, messages.get(choice.reason or "", "No account is available for this job"))


def _handle_provider_error(
    db: Session,
    job: Job,
    queue: JobQueue,
    account: ConnectedAccount,
    exc: ProviderError,
) -> None:
    record_error(account, exc.message)
    if isinstance(exc, ProviderRateLimitError):
        # Respect the provider's own retry guidance; never shorten it.
        account.rate_limited_until = utcnow() + timedelta(seconds=exc.retry_after)
        db.commit()
        nxt = selection.select_account(
            db, job.user_id, job.requested_provider, job.requested_model, IMAGE_GENERATION
        )
        if nxt.account is not None:
            _retry_later(db, job, queue, 1.0, f"{account.label} is rate limited")
        elif nxt.retry_at is not None:
            wait = (nxt.retry_at - utcnow()).total_seconds()
            _retry_later(db, job, queue, wait, "All matching accounts are rate limited")
        else:
            _fail(db, job, exc.message)
    elif isinstance(exc, ProviderAuthError):
        account.status = AccountStatus.INVALID.value
        db.commit()
        nxt = selection.select_account(
            db, job.user_id, job.requested_provider, job.requested_model, IMAGE_GENERATION
        )
        if nxt.account is not None or nxt.reason == selection.RATE_LIMITED:
            _retry_later(db, job, queue, 1.0, f"{account.label} credentials were rejected")
        else:
            _fail(db, job, "All matching accounts have invalid credentials")
    elif isinstance(exc, ProviderTransientError):
        db.commit()
        _retry_later(db, job, queue, min(5 * 2**job.attempts, 300), exc.message)
    elif isinstance(exc, ProviderRequestError):
        db.commit()
        _fail(db, job, exc.message)
    else:
        db.commit()
        _fail(db, job, exc.message)
