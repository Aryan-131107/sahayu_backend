"""
main.py — FastAPI Application Entry Point for Cooperative Gig Services Platform
SIH 2026 Problem Statement 26089
"""

from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import verify_connection, get_db
from app.models import Skill
from app.schemas import SkillResponse
from app.routers import (
    auth,
    customers,
    workers,
    services,
    availability,
    bookings,
    reviews,
    matching,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle handler."""
    try:
        pg_version = verify_connection()
        print(f"[OK] Database connected: {str(pg_version)[:60]}...")
    except Exception as e:
        print(f"[WARNING] Database connection on startup: {e}")
    yield
    print("[INFO] Application shutdown complete.")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="""
## Cooperative Gig Services Platform (SIH 2026 - Problem Statement 26089)

An explainable, transparent, and fair gig services recommendation system for household and community trades.

### Core Features:
- **JWT Authentication & Role Guarding** for Customers and Workers
- **Explainable 6-Parameter Matching Engine**:
  $$\\text{matching\\_score} = 0.35 \\times \\text{skill} + 0.20 \\times \\text{availability} + 0.15 \\times \\text{experience} + 0.15 \\times \\text{rating} + 0.10 \\times \\text{distance} + 0.05 \\times \\text{price}$$
- **Double Booking Guard**: Prevents overlapping slots on the same date/time.
- **Review Integrity**: Restricts reviews to completed bookings with 1-to-1 enforcement.
- **Worker Slot & Availability Calendar**
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── API V1 Sub-Router (/api/...) ─────────────────────────────────────
api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(workers.router)
api_router.include_router(services.router)
api_router.include_router(availability.router)
api_router.include_router(bookings.router)
api_router.include_router(reviews.router)
api_router.include_router(matching.router)


@api_router.get("/skills", response_model=List[SkillResponse], tags=["Skills"], summary="List all skills (/api/skills)")
def api_get_skills(db: Session = Depends(get_db)):
    return db.query(Skill).order_by(Skill.skill_name).all()


@api_router.get("/health", tags=["System"], summary="API health status (/api/health)")
def api_health_check():
    try:
        db_version = verify_connection()
        return {
            "status": "healthy",
            "database": "connected",
            "postgres_version": str(db_version)[:50],
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


app.include_router(api_router)

# ── Direct Root Routes (Backwards Compatibility & Direct Access) ─────
app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(workers.router)
app.include_router(services.router)
app.include_router(bookings.router)
app.include_router(reviews.router)
app.include_router(availability.router)
app.include_router(matching.router)


@app.get("/skills", response_model=List[SkillResponse], tags=["Skills"], summary="List all skills")
def root_get_skills(db: Session = Depends(get_db)):
    return db.query(Skill).order_by(Skill.skill_name).all()


@app.get("/health", tags=["System"], summary="System health check")
def health_check():
    try:
        db_version = verify_connection()
        return {
            "status": "healthy",
            "database": "connected",
            "postgres_version": str(db_version)[:50],
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/", tags=["System"], summary="API Root info")
def root():
    return {
        "message": "Cooperative Gig Services API is running.",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "api_v1": "/api",
        "health": "/health",
    }
