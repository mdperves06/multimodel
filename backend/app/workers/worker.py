"""Worker process: `python -m app.workers.worker`."""

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.models import Job, JobStatus
from app.models.base import utcnow
from app.security.redaction import configure_logging
from app.workers.processor import process_job
from app.workers.queue import JobQueue

logger = logging.getLogger(__name__)
STUCK_AFTER = timedelta(minutes=15)


def recover_stuck_jobs(session_factory: sessionmaker[Session], queue: JobQueue) -> int:
    """Re-queue jobs left in `processing` by a worker that died mid-run."""
    recovered = 0
    with session_factory() as db:
        for job in db.scalars(select(Job).where(Job.status == JobStatus.PROCESSING.value)):
            last = job.events[-1]["at"] if job.events else None
            last_dt = utcnow() - STUCK_AFTER * 2 if last is None else datetime.fromisoformat(last)
            if utcnow() - last_dt > STUCK_AFTER:
                job.status = JobStatus.RETRYING.value
                queue.enqueue(job.id)
                recovered += 1
        db.commit()
    return recovered


def run_worker(stop: threading.Event | None = None, poll_timeout: int = 1) -> None:
    stop = stop or threading.Event()
    queue = JobQueue()
    factory = get_session_factory()
    recovered = recover_stuck_jobs(factory, queue)
    if recovered:
        logger.info("recovered %d stuck job(s)", recovered)
    logger.info("worker started")
    while not stop.is_set():
        try:
            queue.promote_due()
            job_id = queue.dequeue(timeout=poll_timeout)
            if job_id:
                process_job(job_id, factory, queue)
        except Exception:
            logger.exception("worker loop error")
            stop.wait(2)
    logger.info("worker stopped")


def start_embedded_worker() -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()
    thread = threading.Thread(target=run_worker, args=(stop,), name="embedded-worker", daemon=True)
    thread.start()
    return thread, stop


if __name__ == "__main__":
    configure_logging()
    run_worker()
