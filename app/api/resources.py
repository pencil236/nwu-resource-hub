import logging
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.security import create_token, decode_token
from app.db import get_db
from app.models import ProcessingJob, Resource, ResourceStatus, User
from app.schemas import DownloadTicket, ResourceUpdate, ResourceView
from app.services.audit import add_audit
from app.services.rate_limit import enforce_rate_limit
from app.services.storage import get_storage
from app.worker import process_resource, process_resource_now

router = APIRouter(prefix="/resources", tags=["resources"])
logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".pdf", ".docx", ".pptx", ".xlsx", ".png", ".jpg", ".jpeg"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
}


def _has_valid_signature(suffix: str, data: bytes) -> bool:
    if suffix == ".pdf":
        return data.startswith(b"%PDF-")
    if suffix in {".docx", ".pptx", ".xlsx"}:
        return data.startswith(b"PK\x03\x04")
    if suffix == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    return False


def _get_visible_resource(db: Session, resource_id: str, user: User) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在")
    if (
        resource.status != ResourceStatus.PUBLISHED
        and resource.owner_id != user.id
        and not user.is_admin
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在")
    return resource


@router.get("", response_model=list[ResourceView])
def list_resources(
    mine: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Resource]:
    stmt = select(Resource).order_by(Resource.created_at.desc()).limit(100)
    if mine:
        stmt = stmt.where(Resource.owner_id == user.id)
    else:
        stmt = stmt.where(Resource.status == ResourceStatus.PUBLISHED)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ResourceView, status_code=201)
async def upload_resource(
    title: str = Form(min_length=1, max_length=200),
    description: str = Form(default="", max_length=3000),
    experience: str = Form(default="", max_length=3000),
    course: str | None = Form(default=None, max_length=120),
    category: str | None = Form(default=None, max_length=80),
    tags: str = Form(default="", max_length=500),
    rights_confirmed: bool = Form(),
    file: UploadFile = File(),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Resource:
    enforce_rate_limit(f"upload:{user.id}", 20, 3600)
    if not rights_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "必须确认拥有资源分享权限")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES or file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不支持的文件格式")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "文件超过大小限制")
    if not _has_valid_signature(suffix, data):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件内容与格式不匹配")
    used_bytes = (
        db.scalar(
            select(func.coalesce(func.sum(Resource.size_bytes), 0)).where(
                Resource.owner_id == user.id
            )
        )
        or 0
    )
    quota_bytes = get_settings().user_storage_quota_mb * 1024 * 1024
    if used_bytes + len(data) > quota_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "个人存储空间已达到上限")
    resource_id = str(uuid.uuid4())
    object_key = f"{user.id}/{resource_id}/{uuid.uuid4().hex}{suffix}"
    storage = get_storage()
    storage.put(object_key, data, file.content_type or "application/octet-stream")
    resource = Resource(
        id=resource_id,
        owner_id=user.id,
        title=title,
        description=description,
        experience=experience,
        course=course,
        category=category,
        tags=tags,
        original_filename=Path(file.filename or "resource").name,
        content_type=file.content_type or "application/octet-stream",
        object_key=object_key,
        size_bytes=len(data),
        rights_confirmed=True,
    )
    try:
        db.add(resource)
        db.flush()
        db.add(ProcessingJob(resource_id=resource.id))
        add_audit(
            db,
            "resource.upload",
            "resource",
            resource.id,
            user.id,
            {"rights_confirmed": True},
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(object_key)
        raise
    db.refresh(resource)
    if get_settings().enable_background_tasks:
        cast(Any, process_resource).delay(resource.id)
    else:
        try:
            process_resource_now(resource.id)
        except Exception as exc:
            logger.warning("Synchronous resource processing failed", exc_info=exc)
        db.refresh(resource)
    return resource


@router.get("/{resource_id}", response_model=ResourceView)
def get_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Resource:
    return _get_visible_resource(db, resource_id, user)


@router.patch("/{resource_id}", response_model=ResourceView)
def update_resource(
    resource_id: str,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Resource:
    resource = _get_visible_resource(db, resource_id, user)
    if resource.owner_id != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权编辑该资源")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(resource, key, value)
    db.commit()
    db.refresh(resource)
    return resource


@router.post("/{resource_id}/confirm", response_model=ResourceView)
def confirm_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Resource:
    resource = _get_visible_resource(db, resource_id, user)
    if resource.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "只能发布自己的资源")
    if resource.status != ResourceStatus.WAITING_CONFIRMATION:
        raise HTTPException(status.HTTP_409_CONFLICT, "资源尚未完成解析")
    resource.status = ResourceStatus.PUBLISHED
    add_audit(db, "resource.publish", "resource", resource.id, user.id)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("/{resource_id}/download")
def download_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    resource = _get_visible_resource(db, resource_id, user)
    storage = get_storage()
    download_url = storage.download_url(resource.object_key)
    if download_url:
        return RedirectResponse(download_url, status_code=307)
    return Response(
        storage.get(resource.object_key),
        media_type=resource.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(resource.original_filename)}"
        },
    )


@router.post("/{resource_id}/download-ticket", response_model=DownloadTicket)
def create_download_ticket(
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> DownloadTicket:
    resource = _get_visible_resource(db, resource_id, user)
    storage = get_storage()
    url = storage.download_url(resource.object_key)
    if url is None:
        token = create_token(f"{user.id}:{resource.id}", "download", timedelta(minutes=5))
        url = f"/api/resources/download/{token}"
    return DownloadTicket(url=url)


@router.get("/download/{token}")
def download_with_ticket(token: str, db: Session = Depends(get_db)) -> Response:
    try:
        payload = decode_token(token, "download")
        _user_id, resource_id = payload["sub"].split(":", 1)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "下载凭证无效或已过期") from exc
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在")
    return Response(
        get_storage().get(resource.object_key),
        media_type=resource.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(resource.original_filename)}"
        },
    )


@router.delete("/{resource_id}", status_code=204)
def delete_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    resource = _get_visible_resource(db, resource_id, user)
    if resource.owner_id != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权删除该资源")
    get_storage().delete(resource.object_key)
    add_audit(db, "resource.delete", "resource", resource.id, user.id)
    db.delete(resource)
    db.commit()
