"""
routers/admin.py — Platform Administrator Management & Dashboard Endpoints
Protected by role-based admin authorization (require_admin).
"""
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.database import get_db
from app.models import WorkerData, CustomerData, Booking, Service, Skill, RatingReview, WorkerSkill, Availability
from app.schemas import (
    AdminStatsResponse, AdminWorkerItem, AdminBookingItem, PaymentBreakdown,
    AdminPaymentItem, ServiceCreate, ServiceResponse, ServiceUpdate,
    AdminReviewItem, WorkerVerificationResponse, WorkerVerificationAction,
    WorkerStatusUpdate, WorkerSkillResponse, SkillResponse
)
from app.core.auth import require_admin, AuthUser

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

# Cooperative platform fee constant (10.0%)
PLATFORM_FEE_PERCENT = 10.0


def _calculate_fee_breakdown(amount: float, payment_status: str) -> PaymentBreakdown:
    """Calculate platform fee (10%) and worker earnings (90%) ensuring total equals customer paid amount."""
    amt = float(amount) if amount is not None else 0.0
    fee = round(amt * (PLATFORM_FEE_PERCENT / 100.0), 2)
    earnings = round(amt - fee, 2)
    return PaymentBreakdown(
        customer_paid_amount=amt,
        platform_fee=fee,
        worker_earnings=earnings,
        platform_fee_percent=PLATFORM_FEE_PERCENT,
        payment_status=payment_status,
    )


# ─────────────────────────────────────────────────────────
# 1. DASHBOARD STATISTICS
# ─────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Get aggregated platform statistics for Admin Dashboard",
)
def get_admin_stats(
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns real-time platform statistics:
    - Worker counts (total, verified, pending, active)
    - Customer and booking totals
    - Financial totals (customer payments, worker earnings, platform fees)
    """
    total_workers = db.query(WorkerData).count()
    verified_workers = (
        db.query(WorkerData)
        .filter(or_(WorkerData.verification_status == "VERIFIED", WorkerData.is_verified == True))
        .count()
    )
    pending_workers = (
        db.query(WorkerData)
        .filter(WorkerData.verification_status == "PENDING")
        .count()
    )
    active_workers = db.query(WorkerData).filter(WorkerData.is_active == True).count()
    total_customers = db.query(CustomerData).count()
    total_bookings = db.query(Booking).count()
    completed_bookings = db.query(Booking).filter(Booking.status == "COMPLETED").count()

    # Sum of completed payments
    completed_sum = (
        db.query(func.coalesce(func.sum(Booking.amount), 0.0))
        .filter(Booking.status == "COMPLETED")
        .scalar()
    )
    total_customer_payments = float(completed_sum)
    total_platform_fees = round(total_customer_payments * (PLATFORM_FEE_PERCENT / 100.0), 2)
    total_worker_earnings = round(total_customer_payments - total_platform_fees, 2)

    return AdminStatsResponse(
        total_workers=total_workers,
        verified_workers=verified_workers,
        pending_workers=pending_workers,
        pending_verifications=pending_workers,
        active_workers=active_workers,
        total_customers=total_customers,
        total_bookings=total_bookings,
        completed_bookings=completed_bookings,
        total_customer_payments=total_customer_payments,
        total_worker_earnings=total_worker_earnings,
        total_platform_fees=total_platform_fees,
        total_revenue=total_platform_fees,
    )


# ─────────────────────────────────────────────────────────
# 2. WORKER MANAGEMENT & VERIFICATION
# ─────────────────────────────────────────────────────────

def _format_admin_worker(w: WorkerData, db: Session) -> AdminWorkerItem:
    """Helper to format worker details for admin panel."""
    skills_data = (
        db.query(WorkerSkill, Skill)
        .join(Skill, WorkerSkill.skill_id == Skill.skill_id)
        .filter(WorkerSkill.worker_id == w.worker_id)
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

    rating_stats = (
        db.query(
            func.avg(RatingReview.rating).label("avg_rating"),
            func.count(RatingReview.review_id).label("total_reviews"),
        )
        .filter(RatingReview.worker_id == w.worker_id)
        .first()
    )
    avg_rating = float(rating_stats.avg_rating) if rating_stats and rating_stats.avg_rating is not None else None
    total_reviews = int(rating_stats.total_reviews) if rating_stats and rating_stats.total_reviews is not None else 0

    return AdminWorkerItem(
        worker_id=w.worker_id,
        name=w.name,
        phone=w.phone,
        email=w.email,
        experience_years=w.experience_years or 0,
        hourly_rate=float(w.hourly_rate) if w.hourly_rate is not None else 250.00,
        address=w.address,
        city=w.city,
        latitude=float(w.latitude) if w.latitude is not None else 23.181500,
        longitude=float(w.longitude) if w.longitude is not None else 79.986400,
        is_verified=bool(w.is_verified),
        verification_status=w.verification_status or ("VERIFIED" if w.is_verified else "PENDING"),
        verification_type=w.verification_type or "DEMO_SHRAMIK",
        shramik_id=w.shramik_id,
        skill_certificate=w.skill_certificate,
        verified_at=w.verified_at,
        is_active=bool(w.is_active),
        skills=formatted_skills,
        average_rating=round(avg_rating, 2) if avg_rating is not None else None,
        total_reviews=total_reviews,
        created_at=w.created_at,
    )


@router.get(
    "/workers",
    response_model=List[AdminWorkerItem],
    summary="List, search and filter workers for Admin Management",
)
def get_admin_workers(
    search: Optional[str] = Query(None, description="Search by name, phone, email, or Shramik ID"),
    verification_status: Optional[str] = Query(None, description="Filter by status ('PENDING', 'VERIFIED', 'REJECTED')"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skill_id: Optional[int] = Query(None, description="Filter by skill ID"),
    city: Optional[str] = Query(None, description="Filter by city"),
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve all workers with complete administration details, verification status, and skills."""
    query = db.query(WorkerData)

    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(WorkerData.name).like(s),
                func.lower(WorkerData.email).like(s),
                WorkerData.phone.like(s),
                func.lower(WorkerData.shramik_id).like(s),
            )
        )
    if verification_status:
        query = query.filter(func.upper(WorkerData.verification_status) == verification_status.strip().upper())
    if is_active is not None:
        query = query.filter(WorkerData.is_active == is_active)
    if city:
        query = query.filter(func.lower(WorkerData.city) == city.strip().lower())
    if skill_id:
        query = query.join(WorkerSkill, WorkerData.worker_id == WorkerSkill.worker_id).filter(
            WorkerSkill.skill_id == skill_id
        )

    workers = query.order_by(WorkerData.worker_id).all()
    return [_format_admin_worker(w, db) for w in workers]


@router.patch(
    "/workers/{worker_id}/status",
    response_model=AdminWorkerItem,
    summary="Activate or deactivate a worker account",
)
def update_worker_active_status(
    worker_id: int,
    payload: WorkerStatusUpdate,
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Toggle worker active status (e.g. suspend or re-activate)."""
    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker {worker_id} not found.")

    worker.is_active = payload.is_active
    db.commit()
    db.refresh(worker)
    return _format_admin_worker(worker, db)


@router.get(
    "/verifications",
    response_model=List[AdminWorkerItem],
    summary="List all workers with PENDING Shramik verification",
)
def get_pending_verifications(
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return list of workers whose Shramik verification request is pending review."""
    pending_workers = (
        db.query(WorkerData)
        .filter(WorkerData.verification_status == "PENDING")
        .order_by(WorkerData.created_at.desc())
        .all()
    )
    return [_format_admin_worker(w, db) for w in pending_workers]


@router.get(
    "/workers/{worker_id}/verification",
    response_model=WorkerVerificationResponse,
    summary="Get verification details for a worker (Admin)",
)
def admin_get_worker_verification(
    worker_id: int,
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve full verification details for a specific worker."""
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
        message=f"Current status: {worker.verification_status}",
    )


@router.patch(
    "/workers/{worker_id}/verify",
    response_model=WorkerVerificationResponse,
    summary="Approve and mark a worker as VERIFIED",
)
def verify_worker(
    worker_id: int,
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin endpoint to approve worker Shramik / skill verification."""
    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker {worker_id} not found.")

    worker.verification_status = "VERIFIED"
    worker.is_verified = True
    worker.verified_at = datetime.now()

    db.commit()
    db.refresh(worker)

    return WorkerVerificationResponse(
        worker_id=worker.worker_id,
        name=worker.name,
        shramik_id=worker.shramik_id,
        skill_certificate=worker.skill_certificate,
        verification_status="VERIFIED",
        verification_type=worker.verification_type or "DEMO_SHRAMIK",
        verified_at=worker.verified_at,
        is_verified=True,
        message="Worker has been successfully verified.",
    )


@router.patch(
    "/workers/{worker_id}/reject",
    response_model=WorkerVerificationResponse,
    summary="Reject a worker's verification request",
)
def reject_worker_verification(
    worker_id: int,
    payload: Optional[WorkerVerificationAction] = None,
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin endpoint to reject worker verification request."""
    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker {worker_id} not found.")

    worker.verification_status = "REJECTED"
    worker.is_verified = False
    worker.verified_at = None

    db.commit()
    db.refresh(worker)

    reason = payload.rejection_reason if payload and payload.rejection_reason else "Verification rejected by admin."
    return WorkerVerificationResponse(
        worker_id=worker.worker_id,
        name=worker.name,
        shramik_id=worker.shramik_id,
        skill_certificate=worker.skill_certificate,
        verification_status="REJECTED",
        verification_type=worker.verification_type or "DEMO_SHRAMIK",
        verified_at=None,
        is_verified=False,
        message=f"Verification rejected: {reason}",
    )


# ─────────────────────────────────────────────────────────
# 3. BOOKINGS & PAYMENT BREAKDOWN
# ─────────────────────────────────────────────────────────

@router.get(
    "/bookings",
    response_model=List[AdminBookingItem],
    summary="List all platform bookings with transparent payment breakdown",
)
def get_admin_bookings(
    status_filter: Optional[str] = Query(None, description="Filter by booking status"),
    payment_status: Optional[str] = Query(None, description="Filter by payment status"),
    worker_id: Optional[int] = Query(None, description="Filter by worker ID"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieve all bookings with full foreign entity relationships and
    transparent financial breakdown (Customer Payment = Platform Fee + Worker Earnings).
    """
    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
    )

    if status_filter:
        query = query.filter(func.upper(Booking.status) == status_filter.strip().upper())
    if payment_status:
        query = query.filter(func.upper(Booking.payment_status) == payment_status.strip().upper())
    if worker_id:
        query = query.filter(Booking.worker_id == worker_id)
    if customer_id:
        query = query.filter(Booking.customer_id == customer_id)

    bookings = query.order_by(Booking.booking_id.desc()).all()

    results = []
    for b in bookings:
        breakdown = _calculate_fee_breakdown(float(b.amount), b.payment_status)
        results.append(
            AdminBookingItem(
                booking_id=b.booking_id,
                customer_id=b.customer_id,
                customer_name=b.customer.name if b.customer else None,
                customer_phone=b.customer.phone if b.customer else None,
                customer_email=b.customer.email if b.customer else None,
                worker_id=b.worker_id,
                worker_name=b.worker.name if b.worker else None,
                worker_phone=b.worker.phone if b.worker else None,
                service_id=b.service_id,
                service_name=b.service.service_name if b.service else None,
                category=b.service.category if b.service else None,
                booking_date=b.booking_date,
                start_time=b.start_time,
                address=b.address,
                description=b.description,
                amount=float(b.amount),
                customer_paid_amount=breakdown.customer_paid_amount,
                platform_fee=breakdown.platform_fee,
                worker_earnings=breakdown.worker_earnings,
                status=b.status,
                payment_status=b.payment_status,
                created_at=b.created_at,
                payment_breakdown=breakdown,
            )
        )
    return results


@router.get(
    "/payments",
    response_model=List[AdminPaymentItem],
    summary="Get payment transaction history with fee division",
)
def get_admin_payments(
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return full historical payments records with transparent fee and payout division."""
    bookings = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
        .order_by(Booking.booking_id.desc())
        .all()
    )

    results = []
    for b in bookings:
        breakdown = _calculate_fee_breakdown(float(b.amount), b.payment_status)
        results.append(
            AdminPaymentItem(
                booking_id=b.booking_id,
                customer_id=b.customer_id,
                customer_name=b.customer.name if b.customer else None,
                worker_id=b.worker_id,
                worker_name=b.worker.name if b.worker else None,
                service_id=b.service_id,
                service_name=b.service.service_name if b.service else None,
                customer_paid_amount=breakdown.customer_paid_amount,
                platform_fee=breakdown.platform_fee,
                worker_earnings=breakdown.worker_earnings,
                payment_status=b.payment_status,
                payment_date=b.created_at,
            )
        )
    return results


# ─────────────────────────────────────────────────────────
# 4. SERVICE CATALOG MANAGEMENT
# ─────────────────────────────────────────────────────────

@router.get(
    "/services",
    response_model=List[ServiceResponse],
    summary="List all services for Admin Catalog",
)
def get_admin_services(
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve all service catalog offerings including inactive ones."""
    services = db.query(Service).options(joinedload(Service.skill)).order_by(Service.service_id).all()
    return [
        ServiceResponse(
            service_id=s.service_id,
            service_name=s.service_name,
            service=s.service_name,
            description=s.description,
            category=s.category,
            base_price=float(s.base_price),
            estimated_duration=s.estimated_duration or 60,
            is_active=bool(s.is_active),
            skill_id=s.skill_id,
            skill=s.skill,
        )
        for s in services
    ]


@router.post(
    "/services",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service offering (Admin)",
)
def create_admin_service(
    payload: ServiceCreate,
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new standardized service catalog item."""
    skill = db.get(Skill, payload.skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Skill {payload.skill_id} not found.")

    service = Service(
        service_name=payload.service_name,
        description=payload.description,
        category=payload.category or "Household",
        base_price=payload.base_price,
        estimated_duration=payload.estimated_duration or 60,
        is_active=True,
        skill_id=payload.skill_id,
    )
    db.add(service)
    db.commit()
    db.refresh(service)

    return ServiceResponse(
        service_id=service.service_id,
        service_name=service.service_name,
        service=service.service_name,
        description=service.description,
        category=service.category,
        base_price=float(service.base_price),
        estimated_duration=service.estimated_duration or 60,
        is_active=bool(service.is_active),
        skill_id=service.skill_id,
        skill=skill,
    )


@router.patch(
    "/services/{service_id}",
    response_model=ServiceResponse,
    summary="Update or toggle a service offering (Admin)",
)
def update_admin_service(
    service_id: int,
    payload: ServiceUpdate,
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update service catalog fields or toggle active status."""
    service = db.query(Service).options(joinedload(Service.skill)).filter(Service.service_id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Service {service_id} not found.")

    if payload.skill_id is not None:
        skill = db.get(Skill, payload.skill_id)
        if not skill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Skill {payload.skill_id} not found.")
        service.skill_id = payload.skill_id

    if payload.service_name is not None:
        service.service_name = payload.service_name
    if payload.description is not None:
        service.description = payload.description
    if payload.category is not None:
        service.category = payload.category
    if payload.base_price is not None:
        service.base_price = payload.base_price
    if payload.estimated_duration is not None:
        service.estimated_duration = payload.estimated_duration
    if payload.is_active is not None:
        service.is_active = payload.is_active

    db.commit()
    db.refresh(service)

    return ServiceResponse(
        service_id=service.service_id,
        service_name=service.service_name,
        service=service.service_name,
        description=service.description,
        category=service.category,
        base_price=float(service.base_price),
        estimated_duration=service.estimated_duration or 60,
        is_active=bool(service.is_active),
        skill_id=service.skill_id,
        skill=service.skill,
    )


# ─────────────────────────────────────────────────────────
# 5. REVIEWS & RATINGS MODERATION
# ─────────────────────────────────────────────────────────

@router.get(
    "/reviews",
    response_model=List[AdminReviewItem],
    summary="List all platform reviews for Admin Moderation",
)
def get_admin_reviews(
    current_user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve all ratings and reviews with customer, worker, and service context."""
    reviews = (
        db.query(RatingReview)
        .options(
            joinedload(RatingReview.customer),
            joinedload(RatingReview.worker),
            joinedload(RatingReview.booking).joinedload(Booking.service),
        )
        .order_by(RatingReview.review_id.desc())
        .all()
    )

    results = []
    for r in reviews:
        service_name = r.booking.service.service_name if r.booking and r.booking.service else None
        results.append(
            AdminReviewItem(
                review_id=r.review_id,
                booking_id=r.booking_id,
                customer_id=r.customer_id,
                customer_name=r.customer.name if r.customer else None,
                worker_id=r.worker_id,
                worker_name=r.worker.name if r.worker else None,
                service_name=service_name,
                rating=float(r.rating),
                review=r.review,
                created_at=r.created_at,
            )
        )
    return results
