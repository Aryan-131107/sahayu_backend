"""
routers/matching.py — Explainable Matching Recommendations API
"""
from typing import Optional
from datetime import date, time
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import RecommendationResponse
from app.services.matching import get_recommendations

router = APIRouter(prefix="/matching", tags=["Matching & Recommendations"])


@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Get explainable worker recommendations",
)
def get_recommendations_endpoint(
    service_id: int = Query(..., description="Target service ID"),
    latitude: float = Query(..., description="Customer location latitude"),
    longitude: float = Query(..., description="Customer location longitude"),
    booking_date: Optional[date] = Query(None, description="Requested booking date"),
    start_time: Optional[time] = Query(None, description="Requested start time"),
    top_n: int = Query(5, ge=1, le=20, description="Max number of recommendations to return"),
    city: Optional[str] = Query(None, description="Filter by city"),
    db: Session = Depends(get_db),
):
    """
    Executes the 6-parameter explainable scoring formula:
    matching_score = 0.35*skill + 0.20*availability + 0.15*experience + 0.15*rating + 0.10*distance + 0.05*price
    Returns structured breakdown scores (0-100) and human-readable reasoning list.
    """
    recs = get_recommendations(
        db=db,
        service_id=service_id,
        customer_lat=latitude,
        customer_lon=longitude,
        booking_date=booking_date,
        start_time=start_time,
        top_n=top_n,
        city=city,
    )
    return RecommendationResponse(
        service_id=service_id,
        total_found=len(recs),
        recommendations=recs,
    )
