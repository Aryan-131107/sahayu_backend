"""
database.py — SQLAlchemy 2.0 database connection and session management.

HOW IT WORKS:
  1. We read DATABASE_URL from the .env file (never hardcoded).
  2. We create an Engine — the core connection pool to PostgreSQL.
  3. We create a SessionLocal factory — each request gets its own session.
  4. get_db() is a FastAPI dependency that yields a session, then closes it.

USAGE IN ROUTERS:
  from app.database import get_db
  from sqlalchemy.orm import Session
  from fastapi import Depends

  @router.get("/example")
  def my_endpoint(db: Session = Depends(get_db)):
      result = db.execute(text("SELECT ...")).fetchall()
      return result
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Please copy .env.example to .env and fill in your credentials."
    )

# Create the SQLAlchemy engine.
# - pool_pre_ping=True: checks connection health before use (handles stale connections).
# - echo=False: set to True to log all SQL queries for debugging.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)

# SessionLocal is a factory. Calling SessionLocal() creates a new DB session.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,  # We control transactions manually
    autoflush=False,   # We flush manually before commits
)


# Base class for all SQLAlchemy ORM models (Phase 3)
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage:
        @router.get("/something")
        def endpoint(db: Session = Depends(get_db)):
            ...

    The 'yield' ensures the session is always closed after the request,
    even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_connection():
    """
    Utility: Test that the database connection is healthy.
    Called at application startup.
    """
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()")).scalar()
        return result
