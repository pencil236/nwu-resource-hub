from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NWU Resource Hub"
    app_env: str = "development"
    secret_key: str = "development-only-secret-change-me"
    database_url: str = "sqlite:///./data/campus.db"
    redis_url: str = "redis://localhost:6379/0"
    allowed_email_domains: Annotated[list[str], NoDecode] = ["example.edu.cn"]
    admin_emails: Annotated[list[str], NoDecode] = []
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    max_upload_mb: int = 50
    user_storage_quota_mb: int = 500
    storage_backend: str = "local"
    local_storage_path: Path = Path("./data/uploads")
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str = "localhost:9000"
    minio_access_key: str = "campus"
    minio_secret_key: str = "campus-secret"
    minio_bucket: str = "resources"
    minio_secure: bool = False
    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_from: str = "campus-share@example.edu.cn"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: int = 60
    deepseek_max_retries: int = 2
    embedding_model: str = "BAAI/bge-m3"
    clamav_host: str | None = None
    clamav_port: int = 3310
    enable_background_tasks: bool = False
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("allowed_email_domains", "admin_emails", "cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
