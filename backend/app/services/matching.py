"""
services/matching.py — Explainable Rule-Based Matching Engine

Implements the transparent 6-parameter scoring formula for SIH 2026 Problem Statement 26089:
matching_score = 0.35 * skill + 0.20 * availability + 0.15 * experience + 0.15 * rating + 0.10 * distance + 0.05 * price
All sub-scores are normalized to 0–100 and accompanied by explainable reasoning arrays.
"""

import math
from datetime import date, time
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Service, Skill, WorkerData, WorkerSkill, Availability, RatingReview, Booking
from app.schemas import WorkerRecommendation, ScoreBreakdown

# ─────────────────────────────────────────────────────────────────────
# SCORING WEIGHTS (Sum = 1.00)
# ─────────────────────────────────────────────────────────────────────
WEIGHT_SKILL = 0.35
WEIGHT_AVAILABILITY = 0.20
WEIGHT_EXPERIENCE = 0.15
WEIGHT_RATING = 0.15
WEIGHT_DISTANCE = 0.10
WEIGHT_PRICE = 0.05

# Normalization constants
MAX_DISTANCE_KM = 50.0        # Workers beyond this get 0 distance score
MAX_EXPERIENCE_YEARS = 15     # Max experience ceiling
BENCHMARK_MIN_RATE = 150.0    # Lower bound benchmark price (INR)
BENCHMARK_MAX_RATE = 800.0    # Upper bound benchmark price (INR)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two GPS coordinates (in km).
    Accounts for spherical Earth curvature using the Haversine formula.
    """
    R = 6371.0  # Earth radius in km
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def compute_explainable_score(
    worker: WorkerData,
    skill_match: Optional[WorkerSkill],
    distance_km: float,
    avg_rating: Optional[float],
    total_reviews: int,
    is_available: bool,
    service_base_price: float,
) -> Tuple[float, float, ScoreBreakdown, List[str]]:
    """
    Computes explainable 6-parameter score and generates human-readable reasoning.

    Returns:
        (matching_score_100, recommendation_score_0_1, breakdown, reasons)
    """
    reasons: List[str] = []

    # 1. Skill Score (0 - 100) — Weight: 0.35
    if skill_match:
        level = (skill_match.skill_level or "Intermediate").lower()
        if level == "expert":
            skill_score = 100.0
            reasons.append("Certified Expert in required skill")
        elif level == "intermediate":
            skill_score = 90.0
            reasons.append("Exact skill match with verified proficiency")
        else:
            skill_score = 80.0
            reasons.append("Matching skill capability")
    else:
        skill_score = 60.0
        reasons.append("Related skill profile")

    # 2. Availability Score (0 - 100) — Weight: 0.20
    if is_available and worker.is_active:
        availability_score = 100.0
        reasons.append("Available for immediate / requested booking slot")
    elif worker.is_active:
        availability_score = 40.0
        reasons.append("Worker currently on job but active today")
    else:
        availability_score = 0.0
        reasons.append("Currently unavailable")

    # 3. Experience Score (0 - 100) — Weight: 0.15
    exp = worker.experience_years or 0
    exp_ratio = min(exp / MAX_EXPERIENCE_YEARS, 1.0)
    experience_score = round(exp_ratio * 100.0, 2)
    if exp >= 10:
        reasons.append(f"Veteran professional with {exp} years of trade experience")
    elif exp >= 3:
        reasons.append(f"{exp} years of hands-on practical experience")
    elif exp > 0:
        reasons.append(f"{exp} year of field experience")
    else:
        reasons.append("Entry-level verified practitioner")

    # 4. Rating Score (0 - 100) — Weight: 0.15
    if avg_rating is not None and avg_rating > 0:
        rating_score = round(max(0.0, (avg_rating - 1.0) / 4.0 * 100.0), 2)
        reasons.append(f"High customer satisfaction: {avg_rating:.1f}/5.0 ({total_reviews} reviews)")
    else:
        rating_score = 75.0  # Neutral positive prior for newly onboarded workers
        reasons.append("Newly verified worker with top initial platform standing")

    # 5. Distance Score (0 - 100) — Weight: 0.10
    dist_ratio = max(0.0, 1.0 - (distance_km / MAX_DISTANCE_KM))
    distance_score = round(dist_ratio * 100.0, 2)
    if distance_km <= 3.0:
        reasons.append(f"Ultra-close proximity: {distance_km:.1f} km away (Rapid arrival)")
    elif distance_km <= 10.0:
        reasons.append(f"Nearby service provider ({distance_km:.1f} km)")
    else:
        reasons.append(f"Within service zone ({distance_km:.1f} km)")

    # 6. Price Score (0 - 100) — Weight: 0.05
    hourly_rate = float(worker.hourly_rate or 250.00)
    price_span = max(BENCHMARK_MAX_RATE - BENCHMARK_MIN_RATE, 1.0)
    price_ratio = max(0.0, min(1.0, (BENCHMARK_MAX_RATE - hourly_rate) / price_span))
    price_score = round(price_ratio * 100.0, 2)
    if hourly_rate <= service_base_price:
        reasons.append(f"Budget-friendly pricing at ₹{hourly_rate:.0f}/hr")
    else:
        reasons.append(f"Competitive rate at ₹{hourly_rate:.0f}/hr")

    # Verification bonus/mention
    if worker.is_verified:
        reasons.append("Identity & background verified")

    # Compute Total Weighted Score (0 - 100)
    matching_score_100 = round(
        (skill_score * WEIGHT_SKILL)
        + (availability_score * WEIGHT_AVAILABILITY)
        + (experience_score * WEIGHT_EXPERIENCE)
        + (rating_score * WEIGHT_RATING)
        + (distance_score * WEIGHT_DISTANCE)
        + (price_score * WEIGHT_PRICE),
        2
    )
    matching_score_100 = min(max(matching_score_100, 0.0), 100.0)
    recommendation_score_0_1 = round(matching_score_100 / 100.0, 4)

    breakdown = ScoreBreakdown(
        skill_score=skill_score,
        availability_score=availability_score,
        experience_score=experience_score,
        rating_score=rating_score,
        distance_score=distance_score,
        price_score=price_score,
    )

    return matching_score_100, recommendation_score_0_1, breakdown, reasons


def get_recommendations(
    db: Session,
    service_id: int,
    customer_lat: float,
    customer_lon: float,
    booking_date: Optional[date] = None,
    start_time: Optional[time] = None,
    top_n: int = 5,
    city: Optional[str] = None,
) -> List[WorkerRecommendation]:
    """
    Orchestrates the explainable recommendation process.
    """
    from fastapi import HTTPException, status

    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with id {service_id} not found."
        )

    skill = db.get(Skill, service.skill_id)
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill for service {service_id} not found."
        )

    # 1. Fetch workers who have the skill and are active
    worker_skill_query = (
        db.query(WorkerData, WorkerSkill)
        .join(WorkerSkill, WorkerData.worker_id == WorkerSkill.worker_id)
        .filter(WorkerSkill.skill_id == skill.skill_id)
        .filter(WorkerData.is_active == True)
    )
    if city:
        worker_skill_query = worker_skill_query.filter(
            func.lower(WorkerData.city) == city.lower()
        )

    eligible_worker_pairs = worker_skill_query.all()
    if not eligible_worker_pairs:
        return []

    worker_ids = [w.worker_id for w, _ in eligible_worker_pairs]

    # 2. Check real-time availability / slot conflicts
    # Fetch active bookings or availability slots
    avail_records = (
        db.query(Availability)
        .filter(Availability.worker_id.in_(worker_ids))
        .all()
    )
    avail_map: Dict[int, bool] = {a.worker_id: a.is_available for a in avail_records}

    # If slot time is given, also check overlapping active bookings
    busy_workers = set()
    if booking_date:
        conflict_query = (
            db.query(Booking.worker_id)
            .filter(Booking.worker_id.in_(worker_ids))
            .filter(Booking.booking_date == booking_date)
            .filter(Booking.status.in_(["PENDING", "ACCEPTED", "IN_PROGRESS"]))
        )
        if start_time:
            conflict_query = conflict_query.filter(Booking.start_time == start_time)
        conflicts = conflict_query.all()
        busy_workers = {c[0] for c in conflicts}

    # 3. Batch query average ratings and review counts
    avg_ratings_query = (
        db.query(
            RatingReview.worker_id,
            func.avg(RatingReview.rating).label("avg_rating"),
            func.count(RatingReview.review_id).label("total_reviews"),
        )
        .filter(RatingReview.worker_id.in_(worker_ids))
        .group_by(RatingReview.worker_id)
        .all()
    )
    rating_map = {row.worker_id: (float(row.avg_rating), int(row.total_reviews)) for row in avg_ratings_query}

    # Fallback to join via bookings if direct worker_id in review is null
    if len(rating_map) < len(worker_ids):
        booking_ratings_query = (
            db.query(
                Booking.worker_id,
                func.avg(RatingReview.rating).label("avg_rating"),
                func.count(RatingReview.review_id).label("total_reviews"),
            )
            .join(RatingReview, RatingReview.booking_id == Booking.booking_id)
            .filter(Booking.worker_id.in_(worker_ids))
            .group_by(Booking.worker_id)
            .all()
        )
        for row in booking_ratings_query:
            if row.worker_id not in rating_map:
                rating_map[row.worker_id] = (float(row.avg_rating), int(row.total_reviews))

    # 4. Score all workers
    recommendations: List[WorkerRecommendation] = []
    service_price = float(service.base_price or 250.00)

    for worker, worker_skill in eligible_worker_pairs:
        # Determine availability
        is_worker_avail = avail_map.get(worker.worker_id, True)
        if worker.worker_id in busy_workers:
            is_worker_avail = False

        distance_km = haversine_distance(
            customer_lat, customer_lon,
            float(worker.latitude), float(worker.longitude)
        )

        rating_data = rating_map.get(worker.worker_id, (None, 0))
        avg_rating = rating_data[0]
        total_reviews = rating_data[1]

        matching_score_100, rec_score_0_1, breakdown, reasons = compute_explainable_score(
            worker=worker,
            skill_match=worker_skill,
            distance_km=distance_km,
            avg_rating=avg_rating,
            total_reviews=total_reviews,
            is_available=is_worker_avail,
            service_base_price=service_price,
        )

        recommendations.append(
            WorkerRecommendation(
                worker_id=worker.worker_id,
                name=worker.name,
                phone=worker.phone,
                experience_years=worker.experience_years,
                hourly_rate=float(worker.hourly_rate or 250.00),
                is_verified=worker.is_verified,
                is_available=is_worker_avail,
                distance_km=round(distance_km, 2),
                average_rating=round(avg_rating, 2) if avg_rating else None,
                total_reviews=total_reviews,
                recommendation_score=rec_score_0_1,
                matching_score=matching_score_100,
                relevant_skill=skill.skill_name,
                score_breakdown=breakdown,
                reasons=reasons,
            )
        )

    # Sort descending by matching score
    recommendations.sort(key=lambda r: r.matching_score, reverse=True)
    return recommendations[:top_n]
