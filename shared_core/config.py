"""
Centralized configuration for Video Creator Platform.
All environment variables are defined here with validated defaults.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = ""
    pool_size: int = 5
    max_overflow: int = 10
    pool_pre_ping: bool = True
    echo: bool = False

    def __post_init__(self):
        if not self.url:
            object.__setattr__(
                self, "url",
                os.getenv("DATABASE_URL", "postgresql://admin:password123@localhost:5432/video_creator"),
            )


@dataclass(frozen=True)
class RedisConfig:
    url: str = ""

    def __post_init__(self):
        if not self.url:
            object.__setattr__(
                self, "url",
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            )


@dataclass(frozen=True)
class MinIOConfig:
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket_name: str = ""
    secure: bool = False

    def __post_init__(self):
        if not self.endpoint:
            object.__setattr__(self, "endpoint", os.getenv("MINIO_ENDPOINT", "localhost:9000"))
        if not self.access_key:
            object.__setattr__(self, "access_key", os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
        if not self.secret_key:
            object.__setattr__(self, "secret_key", os.getenv("MINIO_SECRET_KEY", "minioadmin"))
        if not self.bucket_name:
            object.__setattr__(self, "bucket_name", os.getenv("MINIO_BUCKET_NAME", "videos"))
        secure_env = os.getenv("MINIO_SECURE", "false")
        object.__setattr__(self, "secure", secure_env.lower() == "true")


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = ""
    model_name: str = ""

    def __post_init__(self):
        if not self.base_url:
            object.__setattr__(self, "base_url", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        if not self.model_name:
            object.__setattr__(self, "model_name", os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M"))


@dataclass(frozen=True)
class AuthConfig:
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    def __post_init__(self):
        if not self.secret_key:
            object.__setattr__(
                self, "secret_key",
                os.getenv("JWT_SECRET_KEY", "super-secret-video-creator-key-replace-in-prod"),
            )


@dataclass(frozen=True)
class AppConfig:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    minio: MinIOConfig = field(default_factory=MinIOConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    """Return cached application settings. Call once at startup."""
    return AppConfig()
