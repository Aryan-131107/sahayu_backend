"""
database.py — SQLAlchemy 2.0 database connection and session management.

Features:
  - Reads DATABASE_URL through the central settings/environment system.
  - No hardcoded database credentials.
  - Works seamlessly both with local .env files and production Render environment variables.
  - Automatically compatible with SQLAlchemy 2.0 and psycopg3.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Please set the DATABASE_URL environment variable "
        "(e.g. in your Render dashboard or local .env file)."
    )

# Create the SQLAlchemy engine using psycopg3
# - pool_pre_ping=True: checks connection health before use (handles idle/stale pool connections).
# - echo=False: set to True if SQL query logging is needed for debugging.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

# SessionLocal factory for request-scoped database sessions
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# Base class for SQLAlchemy ORM models
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency that yields a database session per request and ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_connection():
    """
    Test database connection health. Called during application startup lifecycle.
    """
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()")).scalar()
        return result
