from __future__ import annotations

import base64
import json
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Drovixa"
    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    SERVICE_ROLE: Literal["api", "worker", "scheduler"] = "api"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    RELEASE: str = "drovixa@0.13.0"
    BACKEND_CORS_ORIGINS: list[str] = Field(default_factory=list)
    TRUSTED_HOSTS: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    TRUST_PROXY_HEADERS: bool = False
    FORCE_HTTPS: bool = False
    HSTS_MAX_AGE_SECONDS: int = Field(default=31_536_000, ge=0, le=63_072_000)
    MAX_REQUEST_BODY_BYTES: int = Field(default=2_097_152, ge=16_384, le=52_428_800)

    DATABASE_URL: str = "postgresql+asyncpg://drovixa:drovixa@localhost:5432/drovixa"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    DATABASE_POOL_SIZE: int = Field(default=20, ge=1, le=200)
    DATABASE_MAX_OVERFLOW: int = Field(default=20, ge=0, le=200)
    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(default=30_000, ge=1_000, le=300_000)
    REDIS_SOCKET_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=30)
    REDIS_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=30)

    JWT_SECRET: str = "development-only-jwt-secret-change-me"
    REFRESH_SECRET: str = "development-only-refresh-secret"
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_ISSUER: str = "drovixa-api"
    JWT_AUDIENCE: str = "drovixa-clients"
    ACCESS_TOKEN_MINUTES: int = Field(default=20, ge=5, le=60)
    REFRESH_TOKEN_DAYS: int = Field(default=60, ge=1, le=90)

    FIRST_SUPERUSER_EMAIL: str | None = None
    FIRST_SUPERUSER_PASSWORD: str | None = None
    FIRST_SUPERUSER_NAME: str = "Drovixa Owner"

    RATE_LIMIT_ENABLED: bool = True
    HEALTHCHECK_REDIS_REQUIRED: bool = True
    METRICS_ENABLED: bool = True
    METRICS_TOKEN: str | None = None
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1, ge=0, le=1)
    SENTRY_PROFILES_SAMPLE_RATE: float = Field(default=0.0, ge=0, le=1)

    VIDEO_PROVIDER: Literal["mux", "cloudflare_stream"] = "mux"
    VIDEO_API_TIMEOUT_SECONDS: int = Field(default=20, ge=5, le=120)
    VIDEO_UPLOAD_MAX_BYTES: int = Field(default=10_737_418_240, ge=1)
    VIDEO_UPLOAD_MAX_DURATION_SECONDS: int = Field(default=14_400, ge=60, le=86_400)
    VIDEO_PLAYBACK_TOKEN_TTL_SECONDS: int = Field(default=900, ge=60, le=86_400)
    VIDEO_WEBHOOK_TOLERANCE_SECONDS: int = Field(default=300, ge=30, le=3_600)
    VIDEO_ALLOWED_ORIGINS: list[str] = Field(default_factory=list)
    DEMO_CATALOG_ENABLED: bool = False
    DEMO_MEDIA_BASE_URL: str = "http://localhost:8000/api/v1/demo-media"

    MUX_TOKEN_ID: str | None = None
    MUX_TOKEN_SECRET: str | None = None
    MUX_SIGNING_KEY_ID: str | None = None
    MUX_SIGNING_PRIVATE_KEY_B64: str | None = None
    MUX_WEBHOOK_SECRET: str | None = None
    MUX_UPLOAD_CORS_ORIGIN: str = "*"
    MUX_UPLOAD_TIMEOUT_SECONDS: int = Field(default=21_600, ge=60, le=604_800)
    MUX_VIDEO_QUALITY: Literal["basic", "plus", "premium"] = "basic"
    MUX_MAX_RESOLUTION_TIER: Literal["1080p", "1440p", "2160p"] = "1080p"
    MUX_API_BASE_URL: str = "https://api.mux.com/video/v1"

    CLOUDFLARE_ACCOUNT_ID: str | None = None
    CLOUDFLARE_STREAM_API_TOKEN: str | None = None
    CLOUDFLARE_STREAM_CUSTOMER_CODE: str | None = None
    CLOUDFLARE_STREAM_SIGNING_KEY_ID: str | None = None
    CLOUDFLARE_STREAM_SIGNING_KEY_PEM_B64: str | None = None
    CLOUDFLARE_STREAM_WEBHOOK_SECRET: str | None = None
    CLOUDFLARE_API_BASE_URL: str = "https://api.cloudflare.com/client/v4"

    WATCH_COMPLETION_PERCENTAGE: int = Field(default=90, ge=50, le=100)
    PROGRESS_SYNC_INTERVAL_SECONDS: int = Field(default=15, ge=5, le=60)
    MINIMUM_VIEW_SECONDS: int = Field(default=7, ge=1, le=60)
    DEFAULT_SIMULTANEOUS_STREAM_LIMIT: int = Field(default=1, ge=1, le=20)
    PREMIUM_SIMULTANEOUS_STREAM_LIMIT: int = Field(default=2, ge=1, le=20)
    GEO_COUNTRY_HEADER: str = "CF-IPCountry"

    PAYMENT_PROVIDER: Literal["disabled", "stripe"] = "disabled"
    PAYMENT_API_TIMEOUT_SECONDS: int = Field(default=20, ge=5, le=120)
    PAYMENT_WEBHOOK_TOLERANCE_SECONDS: int = Field(default=300, ge=30, le=3600)
    PAYMENT_SUCCESS_URL: str = "http://localhost:3000/payment/success"
    PAYMENT_CANCEL_URL: str = "http://localhost:3000/payment/cancelled"
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_API_BASE_URL: str = "https://api.stripe.com/v1"

    IAP_VERIFICATION_ENABLED: bool = False
    APPLE_IAP_SHARED_SECRET: str | None = None
    GOOGLE_PLAY_PACKAGE_NAME: str | None = None
    GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64: str | None = None

    PUSH_PROVIDER: Literal["disabled", "firebase"] = "disabled"
    FIREBASE_PROJECT_ID: str | None = None
    FIREBASE_SERVICE_ACCOUNT_JSON_B64: str | None = None
    FIREBASE_DRY_RUN: bool = False
    PUSH_BATCH_SIZE: int = Field(default=500, ge=1, le=500)
    NOTIFICATION_DELIVERY_MODE: Literal["queue", "inline"] = "queue"
    SCHEDULED_NOTIFICATION_POLLING_ENABLED: bool = False
    SCHEDULED_NOTIFICATION_POLL_INTERVAL_SECONDS: int = Field(default=60, ge=30, le=3600)

    ADMOB_ANDROID_REWARDED_AD_UNIT_ID: str | None = None
    ADMOB_IOS_REWARDED_AD_UNIT_ID: str | None = None
    ADMOB_SSV_PUBLIC_KEYS_URL: str = (
        "https://www.gstatic.com/admob/reward/verifier-keys.json"
    )
    ADMOB_SSV_KEY_CACHE_SECONDS: int = Field(default=86_400, ge=300, le=604_800)
    ENGAGEMENT_AUTOMATION_ENABLED: bool = True

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_render_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql://") and "+asyncpg" not in value:
                return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_configuration(self) -> Self:
        if self.APP_ENV in {"staging", "production"}:
            weak_markers = ("development", "change-me", "replace-with")
            for field_name in ("JWT_SECRET", "REFRESH_SECRET"):
                secret = getattr(self, field_name)
                if len(secret) < 32 or any(marker in secret.lower() for marker in weak_markers):
                    raise ValueError(f"{field_name} must be a strong independent secret")
            if self.JWT_SECRET == self.REFRESH_SECRET:
                raise ValueError("JWT_SECRET and REFRESH_SECRET must be different")
            if self.DEBUG:
                raise ValueError("DEBUG must be false outside local development")
            if not self.BACKEND_CORS_ORIGINS:
                raise ValueError("BACKEND_CORS_ORIGINS is required outside development")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("Wildcard CORS origins are not allowed outside development")
            if not self.TRUSTED_HOSTS or "*" in self.TRUSTED_HOSTS:
                raise ValueError("TRUSTED_HOSTS must contain explicit hosts")
            if not self.FORCE_HTTPS:
                raise ValueError("FORCE_HTTPS must be true outside local development")
            if self.METRICS_ENABLED and (not self.METRICS_TOKEN or len(self.METRICS_TOKEN) < 32):
                raise ValueError("METRICS_TOKEN must contain at least 32 characters")
            if self.SERVICE_ROLE == "api" and self.VIDEO_PROVIDER == "mux":
                required = (
                    "MUX_TOKEN_ID",
                    "MUX_TOKEN_SECRET",
                    "MUX_SIGNING_KEY_ID",
                    "MUX_SIGNING_PRIVATE_KEY_B64",
                    "MUX_WEBHOOK_SECRET",
                )
                missing = [name for name in required if not getattr(self, name)]
                if missing:
                    raise ValueError("Mux configuration is incomplete: " + ", ".join(missing))
                if self.MUX_UPLOAD_CORS_ORIGIN == "*":
                    raise ValueError("MUX_UPLOAD_CORS_ORIGIN cannot be '*' outside development")
            if self.SERVICE_ROLE == "api" and self.PAYMENT_PROVIDER == "stripe" and (
                not self.STRIPE_SECRET_KEY or not self.STRIPE_WEBHOOK_SECRET
            ):
                raise ValueError("Stripe payment configuration is incomplete")
            if self.PUSH_PROVIDER == "firebase":
                if not self.FIREBASE_PROJECT_ID or not self.FIREBASE_SERVICE_ACCOUNT_JSON_B64:
                    raise ValueError("Firebase push configuration is incomplete")
                try:
                    decoded = base64.b64decode(
                        self.FIREBASE_SERVICE_ACCOUNT_JSON_B64, validate=True
                    )
                    account = json.loads(decoded.decode("utf-8"))
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("Firebase service account must be valid base64 JSON") from exc
                if account.get("project_id") != self.FIREBASE_PROJECT_ID:
                    raise ValueError("Firebase project ID does not match the service account")
        return self

    @property
    def docs_enabled(self) -> bool:
        return self.APP_ENV != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
