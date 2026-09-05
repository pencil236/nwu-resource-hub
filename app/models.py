import enum
import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ResourceStatus(str, enum.Enum):
    PROCESSING = "processing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PUBLISHED = "published"
    FAILED = "failed"
    HIDDEN = "hidden"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    resources: Mapped[list["Resource"]] = relationship(back_populates="owner")
    resource_likes: Mapped[list["ResourceLike"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    resource_comments: Mapped[list["ResourceComment"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )


class EmailCode(Base):
    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    experience: Mapped[str] = mapped_column(Text, default="")
    course: Mapped[str | None] = mapped_column(String(120), index=True)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(40), default="其他", index=True)
    college: Mapped[str] = mapped_column(String(100), default="通用", index=True)
    major: Mapped[str] = mapped_column(String(100), default="通用", index=True)
    teacher: Mapped[str] = mapped_column(String(100), default="通用", index=True)
    grade: Mapped[str] = mapped_column(String(40), default="通用", index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[str] = mapped_column(String(500), default="")
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus), default=ResourceStatus.PROCESSING, index=True
    )
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_purpose: Mapped[str | None] = mapped_column(Text)
    ai_audience: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    dislike_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped[User] = relationship(back_populates="resources")
    chunks: Mapped[list["ResourceChunk"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )
    likes: Mapped[list["ResourceLike"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )
    dislikes: Mapped[list["ResourceDislike"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )
    comments: Mapped[list["ResourceComment"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class ResourceLike(Base):
    __tablename__ = "resource_likes"
    __table_args__ = (UniqueConstraint("resource_id", "user_id", name="uq_resource_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    resource: Mapped[Resource] = relationship(back_populates="likes")
    user: Mapped[User] = relationship(back_populates="resource_likes")


class ResourceDislike(Base):
    __tablename__ = "resource_dislikes"
    __table_args__ = (UniqueConstraint("resource_id", "user_id", name="uq_resource_dislike"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    resource: Mapped[Resource] = relationship(back_populates="dislikes")


class ResourceHelp(Base):
    __tablename__ = "resource_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    college: Mapped[str] = mapped_column(String(100), default="通用", index=True)
    major: Mapped[str] = mapped_column(String(100), default="通用", index=True)
    course: Mapped[str] = mapped_column(String(120), default="通用", index=True)
    heat_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResourceHelpSupport(Base):
    __tablename__ = "resource_request_supports"
    __table_args__ = (
        UniqueConstraint("request_id", "user_id", name="uq_resource_request_support"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("resource_requests.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResourceComment(Base):
    __tablename__ = "resource_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    resource: Mapped[Resource] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="resource_comments")


class ResourceChunk(Base):
    __tablename__ = "resource_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))

    resource: Mapped[Resource] = relationship(back_populates="chunks")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), index=True
    )
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.PENDING)
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[str] = mapped_column(Text, default="{}")
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
