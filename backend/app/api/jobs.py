import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job, JobStatus, User
from app.schemas.jobs import JobCreate, JobCreated, JobOut, OutputOut, Page
from app.security.deps import get_current_user
from app.services import jobs as svc
from app.services.audit import audit
from app.workers.queue import JobQueue

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_queue() -> JobQueue:
    return JobQueue()


@router.post("", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    body: JobCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    queue: JobQueue = Depends(get_queue),
) -> JobCreated:
    job = svc.create_job(db, user, body, queue)
    audit(
        db,
        "job.create",
        user_id=user.id,
        request=request,
        target_type="job",
        target_id=job.id,
        meta={"provider": body.provider, "model": body.model, "n": body.number_of_outputs},
    )
    return JobCreated(job_id=job.id, status=job.status)


@router.get("", response_model=Page[JobOut])
def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[JobOut]:
    query = select(Job).where(Job.user_id == user.id)
    if status_filter:
        if status_filter not in {s.value for s in JobStatus}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown status")
        query = query.where(Job.status == status_filter)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Job.created_at.desc()).limit(limit).offset(offset))
    return Page[JobOut](items=[svc.job_to_out(j) for j in rows], total=total)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> JobOut:
    return svc.job_to_out(svc.get_owned_job(db, user.id, job_id))


@router.get("/{job_id}/outputs", response_model=list[OutputOut])
def job_outputs(
    job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[OutputOut]:
    job = svc.get_owned_job(db, user.id, job_id)
    return [svc.output_to_out(o) for o in job.outputs]


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    job = svc.cancel_job(db, svc.get_owned_job(db, user.id, job_id))
    audit(db, "job.cancel", user_id=user.id, request=request, target_type="job", target_id=job.id)
    return svc.job_to_out(job)


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(
    job_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    queue: JobQueue = Depends(get_queue),
) -> JobOut:
    job = svc.retry_job(db, svc.get_owned_job(db, user.id, job_id), queue)
    audit(db, "job.retry", user_id=user.id, request=request, target_type="job", target_id=job.id)
    return svc.job_to_out(job)
