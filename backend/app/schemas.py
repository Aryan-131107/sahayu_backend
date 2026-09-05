"""
schemas.py — Pydantic v2 Models for Request Validation & Response Serialization
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ─────────────────────────────────────────────────────────
# AUTH SCHEMAS
# ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, examples=["Rahul Verma"])
    phone: str = Field(..., min_length=10, max_length=20, examples=["9876543210"])
    email: str = Field(..., max_length=150, examples=["user@example.com"])
    password: str = Field(..., min_length=6, examples=["Password123!"])
    role: str = Field("customer", description="'customer' or 'worker'", examples=["customer"])
    experience_years: Optional[int] = Field(0, ge=0, examples=[5])
    hourly_rate: Optional[float] = Field(250.00, gt=0, examples=[300.00])
    address: Optional[str] = Field(None, examples=["Civil Lines, Jabalpur"])
    city: Optional[str] = Field("Jabalpur", examples=["Jabalpur"])
    latitude: Optional[float] = Field(23.181500, examples=[23.181500])
    longitude: Optional[float] = Field(79.986400, examples=[79.986400])
    skill_ids: Optional[List[int]] = Field(default=[], examples=[[1, 2]])


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
    is_active: bool = True
    skill_id: int
    skill: Optional[SkillResponse] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("service", mode="before")
    @classmethod
    def set_service_alias(cls, v, info):
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
    is_verified: bool = False
    verification_status: Optional[Any] = "PENDING"
    verification_type: Optional[str] = "DEMO_SHRAMIK"
    shramik_id: Optional[str] = None
    skill_certificate: Optional[str] = None
    verified_at: Optional[datetime] = None
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
    customer_id: Optional[int] = Field(None, examples=[1])
    worker_id: int = Field(..., examples=[1])
    service_id: int = Field(..., examples=[1])
    booking_date: Optional[date] = Field(None, examples=["2026-08-28"])
    start_time: Optional[time] = Field(None, examples=["10:00:00"])
    address: Optional[str] = Field(None, examples=["123 Civil Lines, Jabalpur"])
    description: Optional[str] = Field(None, examples=["Ceiling fan making squeaking noise"])
    service_lat: Optional[float] = Field(None, examples=[23.1815])
    service_lon: Optional[float] = Field(None, examples=[79.9864])
    amount: float = Field(..., gt=0, examples=[250.00])


# ── Dual-OTP & Slide 3 Transparent Pricing Schemas ─────────────────────

class BookingPricingBreakdown(BaseModel):
    worker_payout: float = Field(199.00, description="Take-home wage directly released to worker")
    platform_tech_fee: float = Field(30.00, description="Platform infrastructure and operational maintenance fee")
    welfare_pool_fee: float = Field(10.00, description="Society Gullak welfare reserve fund contribution")
    total_amount: float = Field(239.00, description="Total amount paid by customer")
    currency: str = Field("INR", description="Currency identifier")


class BookingCreateRequest(BaseModel):
    customer_id: Optional[int] = Field(None, description="Customer ID (auto-resolved from JWT if omitted)", examples=[1])
    worker_id: int = Field(..., description="Assigned gig worker ID", examples=[1])
    service_id: Optional[int] = Field(1, description="Catalog service ID", examples=[1])
    service_scope: str = Field("Electrical Inspection & Fault Diagnosis", examples=["Electrical Inspection & Fault Diagnosis"])
    location: str = Field("Civil Lines, Jabalpur", examples=["Civil Lines, Jabalpur"])
    booking_date: Optional[date] = Field(None, examples=["2026-09-05"])
    start_time: Optional[time] = Field(None, examples=["10:00:00"])
    description: Optional[str] = Field(None, examples=["Electrical fault check and diagnostics"])


class DualOtpBookingResponse(BaseModel):
    booking_id: int
    booking_reference: str
    status: str
    customer_id: int
    worker_id: int
    service_scope: str
    location: str
    start_otp: str = "4821"
    end_otp: str = "9134"
    pricing: BookingPricingBreakdown
    warranty_active: bool = False
    warranty_expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    worker_name: Optional[str] = None
    customer_name: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VerifyStartOtpRequest(BaseModel):
    booking_id: int = Field(..., examples=[1])
    otp: str = Field(..., min_length=4, max_length=6, examples=["4821"])


class VerifyStartOtpResponse(BaseModel):
    booking_id: int
    booking_reference: str
    status: str = "in_progress"
    message: str = "Doorstep arrival verified. Work is now in progress."
    arrival_confirmed: bool = True
    start_time: Optional[datetime] = None


class VerifyEndOtpRequest(BaseModel):
    booking_id: int = Field(..., examples=[1])
    otp: str = Field(..., min_length=4, max_length=6, examples=["9134"])


class VerifyEndOtpResponse(BaseModel):
    booking_id: int
    booking_reference: str
    status: str = "completed"
    message: str = "Job completed successfully. Payment settled and 72-hour warranty activated."
    settlement_summary: Dict[str, Any]
    warranty_active: bool = True
    warranty_expires_at: Optional[datetime] = None


class WelfareMetricsResponse(BaseModel):
    society_id: int = 1
    total_gullak_reserve: float = Field(..., description="Net total balance in society welfare reserve fund")
    total_contributions_count: int = Field(..., description="Total count of welfare contributions recorded")
    governing_body: str = Field("Jabalpur District Cooperative Federation", description="Supervising cooperative governance body")
    currency: str = "INR"
    last_updated: Optional[datetime] = None


class BookingResponse(BaseModel):
    booking_id: int
    booking_reference: Optional[str] = None
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
    start_otp: Optional[str] = None
    end_otp: Optional[str] = None
    worker_payout_amount: Optional[float] = None
    platform_tech_fee: Optional[float] = None
    welfare_pool_fee: Optional[float] = None
    total_amount: Optional[float] = None
    warranty_active: Optional[bool] = False
    warranty_expires_at: Optional[datetime] = None
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
    customer_id: Optional[int] = Field(None, description="Must match customer on booking", examples=[1])
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


# ─────────────────────────────────────────────────────────
# WORKER VERIFICATION SCHEMAS (Demo Shramik / e-Shram)
# ─────────────────────────────────────────────────────────

class WorkerVerificationSubmit(BaseModel):
    worker_id: Optional[int] = Field(None, description="Worker ID to verify (required if not using worker Bearer token)")
    shramik_id: str = Field(..., min_length=4, max_length=50, examples=["SHR-MP-2026-1001"])
    skill: Optional[str] = Field(None, examples=["Electrician"])
    skill_certificate: Optional[str] = Field(None, examples=["CERT-ITI-ELEC-2024"])
    verification_type: Optional[str] = Field("DEMO_SHRAMIK", description="'DEMO_SHRAMIK', 'SKILL_CERTIFICATE', or 'BOTH'")


class WorkerVerificationResponse(BaseModel):
    worker_id: int
    name: str
    shramik_id: Optional[str] = None
    skill_certificate: Optional[str] = None
    verification_status: str = "PENDING"
    verification_type: Optional[str] = "DEMO_SHRAMIK"
    verified_at: Optional[datetime] = None
    is_verified: bool = False
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WorkerVerificationAction(BaseModel):
    rejection_reason: Optional[str] = Field(None, max_length=255, examples=["Invalid document format or mismatch."])


class WorkerStatusUpdate(BaseModel):
    is_active: bool = Field(..., description="Activate or deactivate worker")


# ─────────────────────────────────────────────────────────
# ADMIN DASHBOARD SCHEMAS
# ─────────────────────────────────────────────────────────

class AdminStatsResponse(BaseModel):
    total_workers: int
    verified_workers: int
    pending_workers: int
    pending_verifications: int
    active_workers: int
    total_customers: int
    total_bookings: int
    completed_bookings: int
    total_customer_payments: float
    total_worker_earnings: float
    total_platform_fees: float
    total_revenue: float


class PaymentBreakdown(BaseModel):
    customer_paid_amount: float
    platform_fee: float
    worker_earnings: float
    platform_fee_percent: float = 10.0
    payment_status: str


class AdminPaymentItem(BaseModel):
    booking_id: int
    customer_id: int
    customer_name: Optional[str] = None
    worker_id: int
    worker_name: Optional[str] = None
    service_id: int
    service_name: Optional[str] = None
    customer_paid_amount: float
    platform_fee: float
    worker_earnings: float
    payment_status: str
    payment_date: Optional[datetime] = None


class AdminWorkerItem(BaseModel):
    worker_id: int
    name: str
    phone: str
    email: str
    experience_years: Optional[int] = 0
    hourly_rate: Optional[float] = 250.00
    address: Optional[str] = None
    city: Optional[str] = None
    latitude: float
    longitude: float
    is_verified: bool = False
    verification_status: str = "PENDING"
    verification_type: Optional[str] = "DEMO_SHRAMIK"
    shramik_id: Optional[str] = None
    skill_certificate: Optional[str] = None
    verified_at: Optional[datetime] = None
    is_active: bool = True
    skills: List[WorkerSkillResponse] = []
    average_rating: Optional[float] = None
    total_reviews: int = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminBookingItem(BaseModel):
    booking_id: int
    customer_id: int
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    worker_id: int
    worker_name: Optional[str] = None
    worker_phone: Optional[str] = None
    service_id: int
    service_name: Optional[str] = None
    category: Optional[str] = None
    booking_date: Optional[date] = None
    start_time: Optional[time] = None
    address: Optional[str] = None
    description: Optional[str] = None
    amount: float
    customer_paid_amount: float
    platform_fee: float
    worker_earnings: float
    status: str
    payment_status: str
    created_at: Optional[datetime] = None
    payment_breakdown: PaymentBreakdown

    model_config = ConfigDict(from_attributes=True)


class ServiceUpdate(BaseModel):
    service_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    base_price: Optional[float] = Field(None, gt=0)
    estimated_duration: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    skill_id: Optional[int] = None


class AdminReviewItem(BaseModel):
    review_id: int
    booking_id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    worker_id: Optional[int] = None
    worker_name: Optional[str] = None
    service_name: Optional[str] = None
    rating: float
    review: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
