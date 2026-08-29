"""
app/core/config.py — Central Application Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os


class Settings(BaseSettings):
    APP_TITLE: str = "Cooperative Gig Services API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Cooperative Gig Services Platform for Household & Community Services - "
        "SIH 2026 Problem Statement 26089"
    )
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:sih2025admin@localhost:5432/gig_services"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sih2026_super_secret_jwt_key_cooperative_gig_platform_secure_hash_key_987654321")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
        "*"
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
