import logging
import time
from datetime import UTC, datetime

from celery import Celery
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import (
    EmailCode,
    JobStatus,
    ProcessingJob,
    RefreshToken,
    Resource,
    ResourceChunk,
    ResourceStatus,
    utcnow,
)
from app.services.antivirus import scan_bytes
from app.services.deepseek import deepseek_client
from app.services.documents import chunk_text, extract_text
from app.services.embeddings import embed_texts
from app.services.storage import get_storage

settings = get_settings()
celery_app = Celery("campus_share", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_track_started=True, task_time_limit=900)
celery_app.conf.beat_schedule = {
    "cleanup-expired-auth-records": {
        "task": "cleanup_expired_auth_records",
        "schedule": 86400,
    }
}
logger = logging.getLogger(__name__)


def process_resource_now(resource_id: str) -> None:
    started = time.perf_counter()
    with SessionLocal() as db:
        resource = db.get(Resource, resource_id)
        if resource is None:
            return
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.resource_id == resource_id))
        try:
            data = get_storage().get(resource.object_key)
            if job:
                job.status = JobStatus.RUNNING
                job.attempts += 1
                job.started_at = utcnow()
                db.commit()
            scan_bytes(data)
            if resource.size_bytes > settings.ai_parse_max_mb * 1024 * 1024:
                resource.ai_summary = "文件较大，已跳过 AI 内容解析，请结合上传者说明预览使用。"
                resource.ai_purpose = resource.description or resource.experience
                resource.ai_audience = "请由上传者补充适用人群"
                resource.status = ResourceStatus.WAITING_CONFIRMATION
                resource.failure_reason = None
                if job:
                    job.status = JobStatus.SUCCEEDED
                    job.finished_at = utcnow()
                    job.error = None
                db.commit()
                logger.info(
                    "Skipped AI parsing for large resource",
                    extra={"resource_id": resource_id, "size_bytes": resource.size_bytes},
                )
                return
            text = extract_text(resource.original_filename, data)
            chunks = chunk_text(text)
            if not chunks:
                chunks = [f"{resource.title}\n{resource.description}\n{resource.experience}"]
            vectors = embed_texts(chunks)
            analysis = deepseek_client.analyze(resource.title, "\n\n".join(chunks[:20]))
            db.execute(delete(ResourceChunk).where(ResourceChunk.resource_id == resource.id))
            for position, (content, embedding) in enumerate(zip(chunks, vectors, strict=True)):
                db.add(
                    ResourceChunk(
                        resource_id=resource.id,
                        position=position,
                        content=content,
                        embedding=embedding,
                    )
                )
            resource.ai_summary = analysis.summary
            resource.ai_purpose = analysis.purpose
            resource.ai_audience = analysis.audience
            if not resource.tags and analysis.tags:
                resource.tags = ",".join(analysis.tags)
            resource.status = ResourceStatus.WAITING_CONFIRMATION
            resource.failure_reason = None
            if job:
                job.status = JobStatus.SUCCEEDED
                job.finished_at = utcnow()
                job.error = None
            db.commit()
            logger.info(
                "Resource processing completed",
                extra={
                    "resource_id": resource_id,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
        except Exception as exc:
            logger.exception("Failed to process resource %s", resource_id)
            resource.status = ResourceStatus.FAILED
            resource.failure_reason = str(exc)[:2000]
            if job:
                job.status = JobStatus.FAILED
                job.finished_at = utcnow()
                job.error = str(exc)[:2000]
            db.commit()
            raise


@celery_app.task(bind=True, name="process_resource", max_retries=3)
def process_resource(self, resource_id: str) -> None:
    try:
        process_resource_now(resource_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1))) from exc


@celery_app.task(name="cleanup_expired_auth_records")
def cleanup_expired_auth_records() -> None:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        db.execute(delete(EmailCode).where(EmailCode.expires_at < now))
        db.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))
        db.commit()
