"""
app/core/config.py — Central Application Configuration
All secrets MUST be set as environment variables.
No hardcoded production credentials.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    APP_TITLE: str = "Cooperative Gig Services API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Cooperative Gig Services Platform for Household & Community Services - "
        "SIH 2026 Problem Statement 26089"
    )

    # ── Database ────────────────────────────────────────────
    # REQUIRED on Render — set via Environment Variables dashboard
    DATABASE_URL: str

    # ── JWT Security ────────────────────────────────────────
    # REQUIRED on Render — set via Environment Variables dashboard
    SECRET_KEY: str

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ── Environment ─────────────────────────────────────────
    ENVIRONMENT: str = "production"

    # ── CORS ────────────────────────────────────────────────
    # Comma-separated list of allowed origins, e.g.:
    # ALLOWED_ORIGINS=https://myapp.vercel.app,https://myapp.com
    # Defaults to permissive localhost dev origins only.
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:5173,"
        "http://localhost:8080,"
        "http://localhost:8000,"
        "http://127.0.0.1:3000,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:8080,"
        "http://127.0.0.1:8000"
    )

    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        raw = self.ALLOWED_ORIGINS
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        return origins

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
