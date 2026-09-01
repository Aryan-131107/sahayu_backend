"""
routers/workers.py — Worker Profiles, Skill Attachment, Search, & Recommendations
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models import WorkerData, Availability, WorkerSkill, Skill, RatingReview, Booking
from app.schemas import (
    WorkerResponse, WorkerUpdate, WorkerSkillResponse, WorkerSkillAttach,
    AvailabilityUpdate, AvailabilityResponse, RecommendationResponse,
    WorkerVerificationSubmit, WorkerVerificationResponse
)
from app.services.matching import get_recommendations
from app.core.auth import get_current_user, get_optional_current_user, require_worker, AuthUser

router = APIRouter(prefix="/workers", tags=["Workers"])


def _format_worker_response(worker: WorkerData, db: Session) -> WorkerResponse:
    """Helper to populate worker skills and rating statistics defensively."""
    # Query worker skills
    skills_data = (
        db.query(WorkerSkill, Skill)
        .join(Skill, WorkerSkill.skill_id == Skill.skill_id)
        .filter(WorkerSkill.worker_id == worker.worker_id)
        .all()
    )
    formatted_skills = [
        WorkerSkillResponse(
            skill_id=s.skill_id,
            skill_name=s.skill_name,
            skill_level=ws.skill_level or "Intermediate",
            experience_years=ws.experience_years or 1,
        )
        for ws, s in skills_data
    ]

    # Query ratings
    rating_stats = (
        db.query(
            func.avg(RatingReview.rating).label("avg_rating"),
            func.count(RatingReview.review_id).label("total_reviews"),
        )
        .filter(RatingReview.worker_id == worker.worker_id)
        .first()
    )
    avg_rating = float(rating_stats.avg_rating) if rating_stats and rating_stats.avg_rating is not None else None
    total_reviews = int(rating_stats.total_reviews) if rating_stats and rating_stats.total_reviews is not None else 0

    return WorkerResponse(
        worker_id=worker.worker_id,
        name=worker.name,
        phone=worker.phone,
        email=worker.email,
        experience_years=worker.experience_years or 0,
        experience=worker.experience_years or 0,
        hourly_rate=float(worker.hourly_rate) if worker.hourly_rate is not None else 250.00,
        address=worker.address,
        city=worker.city,
        latitude=float(worker.latitude) if worker.latitude is not None else 23.181500,
        longitude=float(worker.longitude) if worker.longitude is not None else 79.986400,
        is_verified=bool(worker.is_verified),
        verification_status=worker.verification_status or ("VERIFIED" if worker.is_verified else "PENDING"),
        verification_type=worker.verification_type or "DEMO_SHRAMIK",
        shramik_id=worker.shramik_id,
        skill_certificate=worker.skill_certificate,
        verified_at=worker.verified_at,
        is_active=bool(worker.is_active),
        skills=formatted_skills,
        average_rating=round(avg_rating, 2) if avg_rating is not None else None,
        total_reviews=total_reviews,
        created_at=worker.created_at,
    )


@router.get(
    "",
    response_model=List[WorkerResponse],
    summary="List all workers with optional filtering",
)
def get_workers(
    active_only: bool = Query(True, description="Filter to active workers"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    skill: Optional[str] = Query(None, description="Filter by skill name"),
    db: Session = Depends(get_db),
):
    """List service providers with their skills and ratings."""
    query = db.query(WorkerData)
    if active_only:
        query = query.filter(WorkerData.is_active == True)
    if city:
        query = query.filter(func.lower(WorkerData.city) == city.lower())
    if skill:
        query = (
            query.join(WorkerSkill, WorkerData.worker_id == WorkerSkill.worker_id)
            .join(Skill, WorkerSkill.skill_id == Skill.skill_id)
            .filter(func.lower(Skill.skill_name) == skill.lower())
        )

    workers = query.order_by(WorkerData.worker_id).all()
    return [_format_worker_response(w, db) for w in workers]


@router.get(
    "/search",
    response_model=List[WorkerResponse],
    summary="Search workers by skill name",
)
def search_workers(
    skill: str = Query(..., description="Skill name to search for (e.g. 'Electrician')"),
    db: Session = Depends(get_db),
):
    """Find active workers possessing a specific trade skill."""
    skill_record = (
        db.query(Skill)
        .filter(func.lower(Skill.skill_name) == skill.lower().strip())
        .first()
    )
    if not skill_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill}' not found. Check GET /skills for available skills.",
        )

    workers = (
        db.query(WorkerData)
        .join(WorkerSkill, WorkerData.worker_id == WorkerSkill.worker_id)
        .filter(WorkerSkill.skill_id == skill_record.skill_id)
        .filter(WorkerData.is_active == True)
        .all()
    )
    return [_format_worker_response(w, db) for w in workers]


@router.get(
    "/recommend",
    response_model=RecommendationResponse,
    summary="Get top ranked worker recommendations (Explainable Matching Engine)",
)
def recommend_workers(
    service_id: int = Query(..., description="Target service ID"),
    latitude: float = Query(..., description="Customer latitude"),
    longitude: float = Query(..., description="Customer longitude"),
    top_n: int = Query(5, ge=1, le=20, description="Max recommendations"),
    city: Optional[str] = Query(None, description="Optional city filter"),
    db: Session = Depends(get_db),
):
    """
    Executes explainable 6-parameter matching algorithm:
    0.35*skill + 0.20*availability + 0.15*experience + 0.15*rating + 0.10*distance + 0.05*price
    """
    recommendations = get_recommendations(
        db=db,
        service_id=service_id,
        customer_lat=latitude,
        customer_lon=longitude,
        top_n=top_n,
        city=city,
    )
    return RecommendationResponse(
        service_id=service_id,
        total_found=len(recommendations),
        recommendations=recommendations,
    )


@router.get(
    "/me",
    response_model=WorkerResponse,
    summary="Get current authenticated worker profile",
)
def get_current_worker(
    current_user: AuthUser = Depends(require_worker),
    db: Session = Depends(get_db),
):
    """Retrieve the logged-in worker's profile using JWT authentication."""
    worker = db.get(WorkerData, current_user.id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker account not found.",
        )
    return _format_worker_response(worker, db)


@router.get(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Get full worker profile by ID",
)
def get_worker(worker_id: int, db: Session = Depends(get_db)):
    """Retrieve detailed worker profile."""
    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker with id {worker_id} not found.",
        )
    return _format_worker_response(worker, db)


@router.put(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Update worker profile (Protected)",
)
@router.patch(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Partially update worker profile (Protected)",
)
def update_worker(
    worker_id: int,
    payload: WorkerUpdate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Update worker profile information with authorization guard."""
    if current_user and current_user.role == "worker" and current_user.id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update another worker's profile."
        )

    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker with id {worker_id} not found.",
        )

    if payload.name is not None:
        worker.name = payload.name
    if payload.phone is not None:
        worker.phone = payload.phone
    if payload.experience_years is not None:
        worker.experience_years = payload.experience_years
    if payload.hourly_rate is not None:
        worker.hourly_rate = payload.hourly_rate
    if payload.address is not None:
        worker.address = payload.address
    if payload.city is not None:
        worker.city = payload.city
    if payload.latitude is not None:
        worker.latitude = payload.latitude
    if payload.longitude is not None:
        worker.longitude = payload.longitude
    if payload.is_active is not None:
        worker.is_active = payload.is_active

    db.commit()
    db.refresh(worker)
    return _format_worker_response(worker, db)


@router.post(
    "/{worker_id}/skills",
    response_model=WorkerSkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a skill to a worker",
)
def attach_worker_skill(
    worker_id: int,
    payload: WorkerSkillAttach,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Attach or update a skill for a worker."""
    if current_user and current_user.role == "worker" and current_user.id != worker_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify another worker's skills.")

    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")
    skill = db.get(Skill, payload.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found.")

    ws = db.query(WorkerSkill).filter(
        WorkerSkill.worker_id == worker_id,
        WorkerSkill.skill_id == payload.skill_id
    ).first()

    if ws:
        ws.skill_level = payload.skill_level or "Intermediate"
        ws.experience_years = payload.experience_years or 1
    else:
        ws = WorkerSkill(
            worker_id=worker_id,
            skill_id=payload.skill_id,
            skill_level=payload.skill_level or "Intermediate",
            experience_years=payload.experience_years or 1,
        )
        db.add(ws)

    db.commit()
    return WorkerSkillResponse(
        skill_id=skill.skill_id,
        skill_name=skill.skill_name,
        skill_level=ws.skill_level,
        experience_years=ws.experience_years,
    )


@router.delete(
    "/{worker_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a skill from a worker",
)
def remove_worker_skill(
    worker_id: int,
    skill_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Remove a worker-skill association."""
    if current_user and current_user.role == "worker" and current_user.id != worker_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify another worker's skills.")

    ws = db.query(WorkerSkill).filter(
        WorkerSkill.worker_id == worker_id,
        WorkerSkill.skill_id == skill_id
    ).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Worker-Skill association not found.")

    db.delete(ws)
    db.commit()
    return None


@router.patch(
    "/{worker_id}/availability",
    response_model=AvailabilityResponse,
    summary="Update a worker's real-time availability",
)
def update_availability(
    worker_id: int,
    payload: AvailabilityUpdate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Toggle worker availability flag."""
    if current_user and current_user.role == "worker" and current_user.id != worker_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify another worker's availability.")

    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found.")

    avail = db.query(Availability).filter(Availability.worker_id == worker_id).first()
    if not avail:
        avail = Availability(worker_id=worker_id, is_available=payload.is_available)
        db.add(avail)
    else:
        avail.is_available = payload.is_available
        avail.updated_at = func.now()

    db.commit()
    db.refresh(avail)
    return AvailabilityResponse(
        availability_id=avail.availability_id,
        worker_id=avail.worker_id,
        date=avail.date,
        start_time=avail.start_time,
        end_time=avail.end_time,
        is_available=avail.is_available,
        updated_at=avail.updated_at,
    )


# ─────────────────────────────────────────────────────────
# DEMO SHRAMIK / e-SHRAM WORKER VERIFICATION ENDPOINTS
# ─────────────────────────────────────────────────────────

@router.post(
    "/verify",
    response_model=WorkerVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit worker details for Demo Shramik / e-Shram verification",
)
def submit_worker_verification(
    payload: WorkerVerificationSubmit,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit worker for Demo Shramik/e-Shram and skill certification verification.
    Validates worker existence, checks duplicate Shramik IDs, and sets verification status to PENDING.
    """
    target_worker_id = payload.worker_id
    if not target_worker_id:
        if current_user and current_user.role == "worker":
            target_worker_id = current_user.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="worker_id is required or user must be authenticated as a worker.",
            )

    if current_user and current_user.role == "worker" and current_user.id != target_worker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit verification on behalf of another worker.",
        )

    worker = db.get(WorkerData, target_worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker {target_worker_id} not found.")

    if worker.verification_status == "VERIFIED" and worker.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Worker is already verified.",
        )

    shramik_clean = payload.shramik_id.strip()

    # Check for duplicate Shramik ID across other workers
    duplicate = (
        db.query(WorkerData)
        .filter(
            WorkerData.shramik_id == shramik_clean,
            WorkerData.worker_id != target_worker_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A worker with this Shramik / e-Shram ID already exists in the system.",
        )

    # Update worker verification fields
    worker.shramik_id = shramik_clean
    if payload.skill_certificate:
        worker.skill_certificate = payload.skill_certificate.strip()
    if payload.verification_type:
        worker.verification_type = payload.verification_type
    worker.verification_status = "PENDING"
    worker.is_verified = False
    worker.verified_at = None

    db.commit()
    db.refresh(worker)

    return WorkerVerificationResponse(
        worker_id=worker.worker_id,
        name=worker.name,
        shramik_id=worker.shramik_id,
        skill_certificate=worker.skill_certificate,
        verification_status=worker.verification_status,
        verification_type=worker.verification_type,
        verified_at=worker.verified_at,
        is_verified=bool(worker.is_verified),
        message="Verification request submitted successfully. Pending admin review.",
    )


@router.get(
    "/{worker_id}/verification",
    response_model=WorkerVerificationResponse,
    summary="Get worker verification status",
)
def get_worker_verification_status(
    worker_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve current verification status and details for a specific worker."""
    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker {worker_id} not found.")

    return WorkerVerificationResponse(
        worker_id=worker.worker_id,
        name=worker.name,
        shramik_id=worker.shramik_id,
        skill_certificate=worker.skill_certificate,
        verification_status=worker.verification_status or ("VERIFIED" if worker.is_verified else "PENDING"),
        verification_type=worker.verification_type or "DEMO_SHRAMIK",
        verified_at=worker.verified_at,
        is_verified=bool(worker.is_verified),
        message=f"Current status: {worker.verification_status or 'PENDING'}",
    )
