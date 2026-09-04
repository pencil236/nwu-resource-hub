from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import Report, ReportStatus, Resource, ResourceStatus, User, utcnow
from app.schemas import ReportResolve, ReportView, ResourceView
from app.services.audit import add_audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/resources/{resource_id}/hide", response_model=ResourceView)
def hide_resource(
    resource_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Resource:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在")
    resource.status = ResourceStatus.HIDDEN
    add_audit(db, "resource.hide", "resource", resource.id, user.id)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("/reports", response_model=list[ReportView])
def list_reports(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Report]:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return list(db.scalars(select(Report).order_by(Report.created_at.desc())))


@router.patch("/reports/{report_id}", response_model=ReportView)
def resolve_report(
    report_id: int,
    payload: ReportResolve,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Report:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    if payload.status == ReportStatus.PENDING:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "处理结果不能仍为待处理")
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "举报不存在")
    report.status = payload.status
    report.resolution = payload.resolution
    report.resolved_at = utcnow()
    add_audit(db, "report.resolve", "report", str(report.id), user.id)
    db.commit()
    db.refresh(report)
    return report
