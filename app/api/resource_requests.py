from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import ResourceHelp, ResourceHelpSupport, User
from app.schemas import HelpEngagementView, HelpRequestCreate, HelpRequestView
from app.services.audit import add_audit
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/help-requests", tags=["help-requests"])


def _views(db: Session, requests: list[ResourceHelp], user_id: str) -> list[HelpRequestView]:
    if not requests:
        return []
    request_ids = [item.id for item in requests]
    supported_ids = set(
        db.scalars(
            select(ResourceHelpSupport.request_id).where(
                ResourceHelpSupport.user_id == user_id,
                ResourceHelpSupport.request_id.in_(request_ids),
            )
        ).all()
    )
    author_ids = {item.author_id for item in requests}
    authors = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(author_ids))).all()
    }
    return [
        HelpRequestView(
            id=item.id,
            author_id=item.author_id,
            author_name=authors.get(item.author_id, "未知用户"),
            title=item.title,
            description=item.description,
            college=item.college,
            major=item.major,
            course=item.course,
            heat_count=item.heat_count,
            supported_by_me=item.id in supported_ids,
            created_at=item.created_at,
        )
        for item in requests
    ]


@router.get("", response_model=list[HelpRequestView])
def list_help_requests(
    q: str | None = Query(default=None, max_length=200),
    college: str | None = None,
    major: str | None = None,
    course: str | None = None,
    sort_by: str = "hot",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[HelpRequestView]:
    stmt = select(ResourceHelp)
    if q:
        stmt = stmt.where(
            or_(
                ResourceHelp.title.ilike(f"%{q}%"),
                ResourceHelp.description.ilike(f"%{q}%"),
                ResourceHelp.course.ilike(f"%{q}%"),
            )
        )
    for column, value in (
        (ResourceHelp.college, college),
        (ResourceHelp.major, major),
        (ResourceHelp.course, course),
    ):
        if value:
            stmt = stmt.where(column.ilike(f"%{value}%"))
    if sort_by == "newest":
        stmt = stmt.order_by(ResourceHelp.created_at.desc())
    else:
        stmt = stmt.order_by(ResourceHelp.heat_count.desc(), ResourceHelp.created_at.desc())
    items = list(db.scalars(stmt.limit(100)).all())
    return _views(db, items, user.id)


@router.post("", response_model=HelpRequestView, status_code=201)
def create_help_request(
    payload: HelpRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> HelpRequestView:
    enforce_rate_limit(f"help-request:{user.id}", 10, 3600)
    title = payload.title.strip()
    existing = db.scalar(
        select(ResourceHelp).where(func.lower(ResourceHelp.title) == title.lower())
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"已有相似求助 #{existing.id}，请搜索后点击同求",
        )
    item = ResourceHelp(
        author_id=user.id,
        title=title,
        description=payload.description.strip(),
        college=payload.college.strip() or "通用",
        major=payload.major.strip() or "通用",
        course=payload.course.strip() or "通用",
    )
    db.add(item)
    db.flush()
    add_audit(db, "help_request.create", "help_request", str(item.id), user.id)
    db.commit()
    db.refresh(item)
    return _views(db, [item], user.id)[0]


@router.post("/{request_id}/supports", response_model=HelpEngagementView)
def support_help_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> HelpEngagementView:
    item = db.get(ResourceHelp, request_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "求助不存在")
    existing = db.scalar(
        select(ResourceHelpSupport).where(
            ResourceHelpSupport.request_id == item.id,
            ResourceHelpSupport.user_id == user.id,
        )
    )
    if existing is None:
        db.add(ResourceHelpSupport(request_id=item.id, user_id=user.id))
        item.heat_count += 1
        db.commit()
    return HelpEngagementView(supported_by_me=True, heat_count=item.heat_count)


@router.delete("/{request_id}/supports", response_model=HelpEngagementView)
def remove_help_support(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> HelpEngagementView:
    item = db.get(ResourceHelp, request_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "求助不存在")
    existing = db.scalar(
        select(ResourceHelpSupport).where(
            ResourceHelpSupport.request_id == item.id,
            ResourceHelpSupport.user_id == user.id,
        )
    )
    if existing is not None:
        db.delete(existing)
        item.heat_count = max(0, item.heat_count - 1)
        db.commit()
    return HelpEngagementView(supported_by_me=False, heat_count=item.heat_count)


@router.delete("/{request_id}", status_code=204)
def delete_help_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    item = db.get(ResourceHelp, request_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "求助不存在")
    if item.author_id != user.id and not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权删除该求助")
    add_audit(db, "help_request.delete", "help_request", str(item.id), user.id)
    db.delete(item)
    db.commit()
