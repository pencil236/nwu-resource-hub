from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import Report, ReportStatus, Resource, ResourceStatus, User
from app.schemas import ReportCreate, ReportView
from app.services.audit import add_audit
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportView, status_code=201)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Report:
    enforce_rate_limit(f"report:{user.id}", 10, 3600)
    resource = db.get(Resource, payload.resource_id)
    if resource is None or resource.status != ResourceStatus.PUBLISHED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在")
    if resource.owner_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能举报自己的资源")
    existing = db.scalar(
        select(Report).where(
            Report.resource_id == resource.id,
            Report.reporter_id == user.id,
            Report.status == ReportStatus.PENDING,
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "你已经举报过该资源")
    report = Report(
        resource_id=resource.id,
        reporter_id=user.id,
        reason=payload.reason,
        details=payload.details,
    )
    db.add(report)
    db.flush()
    add_audit(db, "report.create", "report", str(report.id), user.id)
    db.commit()
    db.refresh(report)
    return report
