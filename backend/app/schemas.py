"""
schemas.py — Pydantic v2 Models for Request Validation & Response Serialization
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ─────────────────────────────────────────────────────────
# AUTH SCHEMAS
# ─────────────────────────────────────────────────────────

class CustomerRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Rahul Verma"])
    phone: str = Field(..., min_length=10, max_length=20, examples=["9876543210"])
    email: str = Field(..., max_length=150, examples=["customer@example.com"])
    password: str = Field(..., min_length=6, examples=["Password123!"])
    address: Optional[str] = Field(None, examples=["Civil Lines, Jabalpur"])
    city: Optional[str] = Field("Jabalpur", examples=["Jabalpur"])
    latitude: Optional[float] = Field(23.181500, examples=[23.181500])
    longitude: Optional[float] = Field(79.986400, examples=[79.986400])


class WorkerRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, examples=["Rajesh Sharma"])
    phone: str = Field(..., min_length=10, max_length=20, examples=["9123456780"])
    email: str = Field(..., max_length=150, examples=["worker@example.com"])
    password: str = Field(..., min_length=6, examples=["Password123!"])
    experience_years: Optional[int] = Field(0, ge=0, examples=[5])
    hourly_rate: Optional[float] = Field(250.00, gt=0, examples=[300.00])
    address: Optional[str] = Field(None, examples=["Wright Town, Jabalpur"])
    city: Optional[str] = Field("Jabalpur", examples=["Jabalpur"])
    latitude: Optional[float] = Field(23.185000, examples=[23.185000])
    longitude: Optional[float] = Field(79.982000, examples=[79.982000])
    skill_ids: Optional[List[int]] = Field(default=[], examples=[[1, 2]])


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["customer@example.com"])
    password: str = Field(..., examples=["Password123!"])
    role: Optional[str] = Field(None, description="Optional: 'customer' or 'worker'")


class UserProfile(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    role: str
    city: Optional[str] = None
    address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    user: UserProfile


# ─────────────────────────────────────────────────────────
# SKILLS & SERVICES
# ─────────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    skill_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None


class SkillResponse(BaseModel):
    skill_id: int
    skill_name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WorkerSkillResponse(BaseModel):
    skill_id: int
    skill_name: Optional[str] = None
    skill_level: Optional[str] = "Intermediate"
    experience_years: Optional[int] = 1

    model_config = ConfigDict(from_attributes=True)


class WorkerSkillAttach(BaseModel):
    skill_id: int
    skill_level: Optional[str] = Field("Intermediate", examples=["Intermediate", "Expert", "Beginner"])
    experience_years: Optional[int] = Field(1, ge=0, examples=[3])


class ServiceCreate(BaseModel):
    service_name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None
    category: Optional[str] = "Household"
    base_price: float = Field(..., gt=0)
    estimated_duration: Optional[int] = 60
    skill_id: int


class ServiceResponse(BaseModel):
    service_id: int
    service_name: str
    service: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    base_price: float
    estimated_duration: Optional[int] = 60
    skill_id: int
    skill: Optional[SkillResponse] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("service", mode="before")
    @classmethod
    def set_service_alias(cls, v, info):
        # Fallback for backward compatibility
        return v or info.data.get("service_name")


# ─────────────────────────────────────────────────────────
# CUSTOMER SCHEMAS
# ─────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Rahul Verma"])
    phone: str = Field(..., min_length=10, max_length=20, examples=["9876543210"])
    email: str = Field(..., max_length=150, examples=["rahul@example.com"])
    address: Optional[str] = None
    city: Optional[str] = "Jabalpur"
    latitude: Optional[float] = 23.181500
    longitude: Optional[float] = 79.986400


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CustomerResponse(BaseModel):
    customer_id: int
    name: str
    phone: str
    email: str
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────
# WORKER SCHEMAS
# ─────────────────────────────────────────────────────────

class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    experience_years: Optional[int] = None
    hourly_rate: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None


class WorkerResponse(BaseModel):
    worker_id: int
    name: str
    phone: str
    email: str
    experience_years: Optional[int] = 0
    experience: Optional[int] = 0
    hourly_rate: Optional[float] = 250.00
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: float
    longitude: float
    is_verified: bool = True
    verification_status: bool = True
    is_active: bool = True
    skills: Optional[List[WorkerSkillResponse]] = []
    average_rating: Optional[float] = None
    total_reviews: Optional[int] = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────
# AVAILABILITY SCHEMAS
# ─────────────────────────────────────────────────────────

class AvailabilityCreate(BaseModel):
    worker_id: Optional[int] = None
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_available: bool = True


class AvailabilityUpdate(BaseModel):
    is_available: bool = Field(..., examples=[True])


class AvailabilityResponse(BaseModel):
    availability_id: Optional[int] = None
    worker_id: int
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_available: bool = True
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────
# BOOKINGS SCHEMAS
# ─────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    customer_id: int = Field(..., examples=[1])
    worker_id: int = Field(..., examples=[1])
    service_id: int = Field(..., examples=[1])
    booking_date: Optional[date] = Field(None, examples=["2026-08-28"])
    start_time: Optional[time] = Field(None, examples=["10:00:00"])
    address: Optional[str] = Field(None, examples=["123 Civil Lines, Jabalpur"])
    description: Optional[str] = Field(None, examples=["Ceiling fan making squeaking noise"])
    service_lat: Optional[float] = Field(None, examples=[23.1815])
    service_lon: Optional[float] = Field(None, examples=[79.9864])
    amount: float = Field(..., gt=0, examples=[250.00])


class BookingResponse(BaseModel):
    booking_id: int
    customer_id: int
    worker_id: int
    service_id: int
    booking_date: Optional[date] = None
    start_time: Optional[time] = None
    address: Optional[str] = None
    description: Optional[str] = None
    amount: float
    estimated_price: Optional[float] = None
    service_lat: Optional[float] = None
    service_lon: Optional[float] = None
    status: str
    payment_status: str
    created_at: Optional[datetime] = None
    worker_name: Optional[str] = None
    customer_name: Optional[str] = None
    service_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────
# REVIEWS SCHEMAS
# ─────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    booking_id: int = Field(..., examples=[1])
    customer_id: int = Field(..., description="Must match customer on booking", examples=[1])
    rating: float = Field(..., ge=1.0, le=5.0, examples=[4.5])
    review: Optional[str] = Field(None, max_length=500, examples=["Punctual and very neat repair work!"])

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: float) -> float:
        return round(v, 1)


class ReviewResponse(BaseModel):
    review_id: int
    booking_id: int
    customer_id: Optional[int] = None
    worker_id: Optional[int] = None
    rating: float
    review: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WorkerReviewsResponse(BaseModel):
    worker_id: int
    worker_name: str
    average_rating: Optional[float]
    total_reviews: int
    reviews: List[ReviewResponse]

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────
# MATCHING & RECOMMENDATION SCHEMAS
# ─────────────────────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    skill_score: float = Field(..., description="Sub-score (0-100) for skill relevance")
    availability_score: float = Field(..., description="Sub-score (0-100) for availability")
    experience_score: float = Field(..., description="Sub-score (0-100) for experience level")
    rating_score: float = Field(..., description="Sub-score (0-100) for past reviews rating")
    distance_score: float = Field(..., description="Sub-score (0-100) for proximity")
    price_score: float = Field(..., description="Sub-score (0-100) for price competitiveness")


class WorkerRecommendation(BaseModel):
    worker_id: int
    name: str
    phone: Optional[str] = None
    experience_years: Optional[int] = 0
    hourly_rate: Optional[float] = 250.00
    is_verified: bool = True
    is_available: bool = True
    distance_km: float = Field(..., description="Haversine distance in km")
    average_rating: Optional[float] = Field(None, description="Average rating (1-5)")
    total_reviews: Optional[int] = 0
    recommendation_score: float = Field(..., description="Score 0.0 to 1.0 (backward compatible)")
    matching_score: float = Field(..., description="Normalized score 0 to 100")
    relevant_skill: str
    score_breakdown: ScoreBreakdown
    reasons: List[str] = Field(..., description="Explainable reasoning bullet points")

    model_config = ConfigDict(from_attributes=True)


class RecommendationResponse(BaseModel):
    service_id: int
    service_name: Optional[str] = None
    total_found: int = 0
    recommendations: List[WorkerRecommendation]
