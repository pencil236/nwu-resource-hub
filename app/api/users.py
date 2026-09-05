from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db import get_db
from app.models import Resource, ResourceStatus, User
from app.schemas import UserProfileView, UserView

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me/onboarding", response_model=UserView)
def complete_onboarding(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> User:
    user.onboarding_completed = True
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserProfileView)
def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
) -> UserProfileView:
    profile = db.get(User, user_id)
    if profile is None or not profile.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    resource_filter = (
        Resource.owner_id == profile.id,
        Resource.status == ResourceStatus.PUBLISHED,
        Resource.is_anonymous.is_(False),
    )
    resource_count = db.scalar(
        select(func.count()).select_from(Resource).where(*resource_filter)
    ) or 0
    total_likes = db.scalar(
        select(func.coalesce(func.sum(Resource.like_count), 0)).where(*resource_filter)
    ) or 0
    return UserProfileView(
        id=profile.id,
        display_name=profile.display_name,
        resource_count=resource_count,
        total_likes=total_likes,
    )
