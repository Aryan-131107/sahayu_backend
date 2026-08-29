"""
routers/reviews.py — Rating & Review Management with Strict Integrity Rules

BUSINESS RULES ENFORCED:
1. Reviews allowed ONLY for COMPLETED bookings.
2. 1-to-1 Booking Constraint: Prohibits duplicate reviews per booking.
3. Customer Identity Guard: Only the customer who made the booking can review it.
4. Worker Average Rating recalculation and rating statistics.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models import Booking, RatingReview, WorkerData, CustomerData
from app.schemas import ReviewCreate, ReviewResponse, WorkerReviewsResponse
from app.core.auth import get_optional_current_user, AuthUser

router = APIRouter(tags=["Reviews"])


@router.post(
    "/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a rating & review for a completed booking",
)
def create_review(
    payload: ReviewCreate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit customer review with complete validation:
    - Booking must exist
    - Customer must match booking owner
    - Booking status must be COMPLETED
    - Duplicate reviews prohibited
    - Rating must be 1.0 to 5.0
    """
    # 1. Booking exists
    booking = db.get(Booking, payload.booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {payload.booking_id} not found.")

    # 2. Customer match & resolution
    target_customer_id = payload.customer_id
    if not target_customer_id and current_user and current_user.role == "customer":
        target_customer_id = current_user.id

    if target_customer_id is not None and booking.customer_id != target_customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only submit reviews for your own bookings."
        )

    if current_user and current_user.role == "customer" and current_user.id != booking.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated customer identity does not match review author."
        )

    # 3. Status must be COMPLETED
    if booking.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reviews are strictly restricted to COMPLETED bookings. Current status is {booking.status}."
        )

    # 4. 1-to-1 constraint check
    existing_review = (
        db.query(RatingReview)
        .filter(RatingReview.booking_id == payload.booking_id)
        .first()
    )
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This booking has already received a review. Only one review per booking is permitted."
        )

    # 5. Rating bounds
    if payload.rating < 1.0 or payload.rating > 5.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1.0 and 5.0."
        )

    review = RatingReview(
        booking_id=payload.booking_id,
        customer_id=booking.customer_id,
        worker_id=booking.worker_id,
        rating=payload.rating,
        review=payload.review,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get(
    "/reviews/{booking_id}",
    response_model=ReviewResponse,
    summary="Get review for a specific booking",
)
def get_booking_review(booking_id: int, db: Session = Depends(get_db)):
    """Retrieve review for a given booking."""
    review = (
        db.query(RatingReview)
        .filter(RatingReview.booking_id == booking_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="No review found for this booking.")
    return review


@router.get(
    "/workers/{worker_id}/reviews",
    response_model=WorkerReviewsResponse,
    summary="Get all reviews and rating aggregates for a worker",
)
def get_worker_reviews(worker_id: int, db: Session = Depends(get_db)):
    """Retrieve all ratings and reviews for a worker, with aggregate average."""
    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found.")

    reviews = (
        db.query(RatingReview)
        .filter(RatingReview.worker_id == worker_id)
        .order_by(RatingReview.review_id.desc())
        .all()
    )

    # Fallback to join via bookings if legacy records
    if not reviews:
        reviews = (
            db.query(RatingReview)
            .join(Booking, RatingReview.booking_id == Booking.booking_id)
            .filter(Booking.worker_id == worker_id)
            .order_by(RatingReview.review_id.desc())
            .all()
        )

    avg_calc = (
        db.query(func.avg(RatingReview.rating))
        .filter(RatingReview.worker_id == worker_id)
        .scalar()
    )
    if avg_calc is None and reviews:
        avg_calc = sum(float(r.rating) for r in reviews) / len(reviews)

    return WorkerReviewsResponse(
        worker_id=worker_id,
        worker_name=worker.name,
        average_rating=round(float(avg_calc), 2) if avg_calc is not None else None,
        total_reviews=len(reviews),
        reviews=reviews,
    )
