"""
app/core/config.py — Central Application Configuration
All configuration values are read from environment variables (with local .env support).
No hardcoded secrets or production credentials.
"""
import os
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_TITLE: str = "Cooperative Gig Services API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Cooperative Gig Services Platform for Household & Community Services - "
        "SIH 2026 Problem Statement 26089"
    )

    # ── Database Configuration ──────────────────────────────
    # Required in production / Render — supplied via environment variable
    DATABASE_URL: str

    # ── Security / JWT Configuration ────────────────────────
    # Required in production / Render — supplied via environment variable
    SECRET_KEY: str

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ── Environment ─────────────────────────────────────────
    ENVIRONMENT: str = "production"

    # ── CORS Origins ────────────────────────────────────────
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

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """
        Normalize standard PostgreSQL URLs to psycopg3 dialect.
        Ensures compatibility if Render or Supabase supplies postgres:// or postgresql://.
        """
        if not v or not v.strip():
            raise ValueError(
                "DATABASE_URL is not set. Please set the DATABASE_URL environment variable "
                "(e.g. postgresql+psycopg://user:password@host:5432/dbname)."
            )
        v = v.strip()
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+psycopg://", 1)
        elif v.startswith("postgresql://") and not v.startswith("postgresql+psycopg://"):
            v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "SECRET_KEY is not set. Please set the SECRET_KEY environment variable for JWT security."
            )
        return v.strip()

    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS string into a list."""
        raw = self.ALLOWED_ORIGINS
        return [o.strip() for o in raw.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instantiate central application settings
settings = Settings()
