import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    hash_value,
    verify_password,
)
from app.db import get_db
from app.models import EmailCode, RefreshToken, User
from app.schemas import (
    EmailCodeRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserView,
)
from app.services.email import send_verification_code
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_domain(email: str) -> None:
    domain = email.rsplit("@", 1)[-1]
    if domain not in {item.lower() for item in get_settings().allowed_email_domains}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持指定校内邮箱")


def _issue_tokens(db: Session, user: User) -> TokenPair:
    settings = get_settings()
    access = create_token(user.id, "access", timedelta(minutes=settings.access_token_minutes))
    refresh = create_token(user.id, "refresh", timedelta(days=settings.refresh_token_days))
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_value(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register-code", status_code=204)
def request_code(payload: EmailCodeRequest, db: Session = Depends(get_db)) -> None:
    email = _normalize_email(str(payload.email))
    enforce_rate_limit(f"register-code:{email}", 5, 3600)
    _validate_domain(email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    latest = db.scalar(
        select(EmailCode).where(EmailCode.email == email).order_by(EmailCode.created_at.desc())
    )
    now = datetime.now(UTC)
    if latest and (now - latest.created_at.replace(tzinfo=UTC)).total_seconds() < 60:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "验证码发送过于频繁")
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        EmailCode(
            email=email,
            code_hash=hash_value(code),
            expires_at=now + timedelta(minutes=10),
        )
    )
    db.commit()
    send_verification_code(email, code)


@router.post("/register", response_model=TokenPair)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenPair:
    email = _normalize_email(str(payload.email))
    _validate_domain(email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    record = db.scalar(
        select(EmailCode)
        .where(EmailCode.email == email, EmailCode.consumed.is_(False))
        .order_by(EmailCode.created_at.desc())
    )
    now = datetime.now(UTC)
    if record is None or record.expires_at.replace(tzinfo=UTC) < now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    if record.attempts >= 5:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "验证码尝试次数过多")
    record.attempts += 1
    if record.code_hash != hash_value(payload.code):
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误")
    record.consumed = True
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_admin=email in {item.lower() for item in get_settings().admin_emails},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    enforce_rate_limit(f"login:{_normalize_email(str(payload.email))}", 10, 300)
    user = db.scalar(select(User).where(User.email == _normalize_email(str(payload.email))))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        token_payload = decode_token(payload.refresh_token, "refresh")
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "刷新令牌无效") from exc
    record = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_value(payload.refresh_token),
            RefreshToken.revoked.is_(False),
        )
    )
    if record is None or record.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "刷新令牌已失效")
    record.revoked = True
    user = db.get(User, token_payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return _issue_tokens(db, user)


@router.get("/me", response_model=UserView)
def me(user: User = Depends(current_user)) -> User:
    return user
