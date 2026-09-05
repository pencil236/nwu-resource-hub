from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ReportStatus, ResourceStatus


class EmailCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    display_name: str
    is_admin: bool
    onboarding_completed: bool = False


class UserProfileView(BaseModel):
    id: str
    display_name: str
    resource_count: int
    total_likes: int


class ResourceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    experience: str | None = Field(default=None, max_length=3000)
    course: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    resource_type: str | None = Field(default=None, max_length=40)
    college: str | None = Field(default=None, max_length=100)
    major: str | None = Field(default=None, max_length=100)
    teacher: str | None = Field(default=None, max_length=100)
    grade: str | None = Field(default=None, max_length=40)
    year: int | None = Field(default=None, ge=1900, le=2200)
    is_anonymous: bool | None = None
    tags: str | None = Field(default=None, max_length=500)


class ResourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_id: str
    title: str
    description: str
    experience: str
    course: str | None
    category: str | None
    resource_type: str = "其他"
    college: str = "通用"
    major: str = "通用"
    teacher: str = "通用"
    grade: str = "通用"
    year: int | None = None
    is_anonymous: bool = False
    owner_name: str = "匿名同学"
    tags: str
    original_filename: str
    content_type: str
    size_bytes: int
    rights_confirmed: bool
    status: ResourceStatus
    ai_summary: str | None
    ai_purpose: str | None
    ai_audience: str | None
    failure_reason: str | None
    like_count: int = 0
    dislike_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    disliked_by_me: bool = False
    created_at: datetime


class DownloadTicket(BaseModel):
    url: str
    expires_in: int = 300


class EngagementView(BaseModel):
    liked_by_me: bool
    disliked_by_me: bool
    like_count: int
    dislike_count: int
    comment_count: int


class PreviewText(BaseModel):
    text: str
    truncated: bool


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class CommentView(BaseModel):
    id: int
    resource_id: str
    author_id: str
    author_name: str
    content: str
    created_at: datetime


class HelpRequestCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    college: str = Field(default="通用", max_length=100)
    major: str = Field(default="通用", max_length=100)
    course: str = Field(default="通用", max_length=120)


class HelpRequestView(BaseModel):
    id: int
    author_id: str
    author_name: str
    title: str
    description: str
    college: str
    major: str
    course: str
    heat_count: int
    supported_by_me: bool = False
    created_at: datetime


class HelpEngagementView(BaseModel):
    supported_by_me: bool
    heat_count: int


class SearchResult(BaseModel):
    resource: ResourceView
    score: float
    matched_excerpt: str | None = None


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AgentResponse(BaseModel):
    answer: str
    resources: list[SearchResult]


class ReportCreate(BaseModel):
    resource_id: str
    reason: str = Field(min_length=2, max_length=80)
    details: str = Field(default="", max_length=2000)


class ReportResolve(BaseModel):
    status: ReportStatus
    resolution: str = Field(min_length=2, max_length=2000)


class ReportView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resource_id: str
    reporter_id: str
    reason: str
    details: str
    status: ReportStatus
    resolution: str | None
    created_at: datetime
    resolved_at: datetime | None


class SearchToolArguments(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    course: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    file_type: str | None = Field(default=None, max_length=20)


class ResourceDetailsToolArguments(BaseModel):
    resource_id: str
