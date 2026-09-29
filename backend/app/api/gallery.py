import io
import logging
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Job, JobOutput, User
from app.schemas.jobs import DeleteResult, GalleryItem, OutputIds, Page
from app.security.deps import get_current_user
from app.services import jobs as svc
from app.services.audit import audit
from app.services.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["gallery"])

_SERVABLE = {"image/png", "image/jpeg", "image/webp"}


def _owned_output(db: Session, user_id: uuid.UUID, output_id: uuid.UUID) -> JobOutput:
    output = db.scalar(
        select(JobOutput).where(JobOutput.id == output_id, JobOutput.user_id == user_id)
    )
    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Output not found")
    return output


def _delete_outputs(db: Session, outputs: list[JobOutput]) -> int:
    storage = get_storage()
    for output in outputs:
        try:
            storage.delete(output.storage_key)
        except OSError:
            logger.warning("could not delete stored object for output %s", output.id)
        db.delete(output)
    db.commit()
    return len(outputs)


@router.get("/gallery", response_model=Page[GalleryItem])
def gallery(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[GalleryItem]:
    query = select(JobOutput).join(Job).where(JobOutput.user_id == user.id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Job.prompt.ilike(f"%{escaped}%", escape="\\"))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.options(joinedload(JobOutput.job))
        .order_by(JobOutput.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page[GalleryItem](items=[svc.gallery_item(o) for o in rows], total=total)


@router.get("/outputs/{output_id}/file")
def output_file(
    output_id: uuid.UUID,
    download: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    output = _owned_output(db, user.id, output_id)
    try:
        data = get_storage().get(output.storage_key)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is missing from storage") from None
    media_type = output.mime_type if output.mime_type in _SERVABLE else "application/octet-stream"
    ext = media_type.split("/")[-1] if media_type in _SERVABLE else "bin"
    headers = {
        "Cache-Control": "private, max-age=3600",
        "Content-Security-Policy": "default-src 'none'",
    }
    if download:
        headers["Content-Disposition"] = f'attachment; filename="image-{str(output.id)[:8]}.{ext}"'
    return Response(content=data, media_type=media_type, headers=headers)


@router.post("/outputs/download")
def download_many(
    body: OutputIds, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    outputs = list(
        db.scalars(
            select(JobOutput).where(JobOutput.user_id == user.id, JobOutput.id.in_(body.ids))
        )
    )
    if not outputs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching outputs")
    storage = get_storage()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for i, output in enumerate(outputs, start=1):
            try:
                ext = output.storage_key.rsplit(".", 1)[-1]
                archive.writestr(
                    f"image-{i:03d}-{str(output.id)[:8]}.{ext}", storage.get(output.storage_key)
                )
            except FileNotFoundError:
                continue
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="images.zip"'},
    )


@router.post("/outputs/delete", response_model=DeleteResult)
def delete_many(
    body: OutputIds,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeleteResult:
    outputs = list(
        db.scalars(
            select(JobOutput).where(JobOutput.user_id == user.id, JobOutput.id.in_(body.ids))
        )
    )
    count = _delete_outputs(db, outputs)
    audit(db, "output.delete_many", user_id=user.id, request=request, meta={"count": count})
    return DeleteResult(deleted=count)


@router.delete("/outputs/{output_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_output(
    output_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    output = _owned_output(db, user.id, output_id)
    _delete_outputs(db, [output])
    audit(
        db,
        "output.delete",
        user_id=user.id,
        request=request,
        target_type="output",
        target_id=output_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
