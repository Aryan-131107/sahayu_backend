"""
models.py — SQLAlchemy 2.0 ORM Models for Cooperative Gig Services Platform

Maps Python classes to PostgreSQL tables with exact constraints, relationships,
and indices for SIH 2026 Problem Statement 26089.
"""

from datetime import datetime, date, time
from typing import Optional, List
from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey,
    Integer, Numeric, String, Text, Time, TIMESTAMP, UniqueConstraint,
    func
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


class CustomerData(Base):
    """
    Table: customer_data
    Stores customer profiles, credentials, location, and metadata.
    """
    __tablename__ = "customer_data"

    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="Jabalpur")
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True, default=23.181500)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True, default=79.986400)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="customer", cascade="all, delete-orphan")
    reviews: Mapped[List["RatingReview"]] = relationship("RatingReview", back_populates="customer")


class WorkerData(Base):
    """
    Table: worker_data
    Stores gig service worker profiles, credentials, verification, rate, and location.
    """
    __tablename__ = "worker_data"

    worker_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    experience_years: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="Jabalpur")
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False, default=23.181500)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False, default=79.986400)
    hourly_rate: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True, default=250.00)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Demo Shramik / e-Shram & Skill Verification Fields
    shramik_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True, index=True)
    skill_certificate: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)  # PENDING, VERIFIED, REJECTED
    verification_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="DEMO_SHRAMIK")  # DEMO_SHRAMIK, SKILL_CERTIFICATE, BOTH
    verified_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    skills: Mapped[List["WorkerSkill"]] = relationship("WorkerSkill", back_populates="worker", cascade="all, delete-orphan")
    availability_slots: Mapped[List["Availability"]] = relationship("Availability", back_populates="worker", cascade="all, delete-orphan")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="worker")
    reviews: Mapped[List["RatingReview"]] = relationship("RatingReview", back_populates="worker")

    @property
    def experience(self) -> int:
        return self.experience_years or 0


class AdminUser(Base):
    """
    Table: admin_users
    Stores platform administrator accounts and authorization roles.
    """
    __tablename__ = "admin_users"

    admin_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="admin")
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())


class Skill(Base):
    """
    Table: skills
    Master list of vocational skills and trade categories.
    """
    __tablename__ = "skills"

    skill_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    services: Mapped[List["Service"]] = relationship("Service", back_populates="skill")
    worker_skills: Mapped[List["WorkerSkill"]] = relationship("WorkerSkill", back_populates="skill", cascade="all, delete-orphan")
    rate_card_items: Mapped[List["RateCardItem"]] = relationship("RateCardItem", back_populates="skill", cascade="all, delete-orphan")


class WorkerSkill(Base):
    """
    Table: workers_skill
    Junction table for Worker-Skill with proficiency level and experience years.
    """
    __tablename__ = "workers_skill"

    worker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("worker_data.worker_id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skills.skill_id", ondelete="CASCADE"), primary_key=True
    )
    skill_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="Intermediate")
    experience_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1)

    worker: Mapped["WorkerData"] = relationship("WorkerData", back_populates="skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="worker_skills")


class Availability(Base):
    """
    Table: availability
    Slot-based and real-time availability indicator for each worker.
    """
    __tablename__ = "availability"

    availability_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("worker_data.worker_id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, server_default=func.current_date())
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    worker: Mapped["WorkerData"] = relationship("WorkerData", back_populates="availability_slots")


class Service(Base):
    """
    Table: services
    Catalog of standardized household and community services.
    """
    __tablename__ = "services"

    service_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="Household")
    base_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=250.00)
    estimated_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=60)  # minutes
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    skill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skills.skill_id", ondelete="RESTRICT"), nullable=False, index=True
    )

    skill: Mapped["Skill"] = relationship("Skill", back_populates="services")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="service")
    rate_card_items: Mapped[List["RateCardItem"]] = relationship("RateCardItem", back_populates="service")

    @property
    def service(self) -> str:
        return self.service_name


class RateCardItem(Base):
    """
    Table: rate_card_items
    Cooperative-approved rate card for additional labor, replacement parts, and materials.
    Mapped directly to vocational Skill / Service category to prevent skill-card mismatch.
    """
    __tablename__ = "rate_card_items"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skills.skill_id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("services.service_id", ondelete="SET NULL"), nullable=True, index=True
    )
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="LABOR")  # LABOR, MATERIAL, SERVICE
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="unit")  # per unit, per point, per sq ft, fixed
    unit_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    @property
    def rate(self) -> float:
        return float(self.unit_rate)

    skill: Mapped["Skill"] = relationship("Skill", back_populates="rate_card_items")
    service: Mapped[Optional["Service"]] = relationship("Service", back_populates="rate_card_items")
    quotation_items: Mapped[List["QuotationItem"]] = relationship("QuotationItem", back_populates="rate_card_item")


class Booking(Base):
    """
    Table: bookings
    Core gig transaction tracking lifecycle, inspection-first state machine, double-booking guard, and payment status.
    """
    __tablename__ = "bookings"

    booking_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer_data.customer_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    worker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("worker_data.worker_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    service_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("services.service_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    booking_date: Mapped[Optional[date]] = mapped_column(Date, server_default=func.current_date())
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=239.00)
    service_lat: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    service_lon: Mapped[Optional[float]] = mapped_column(Numeric(9, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CONFIRMED", index=True)
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")

    # Dual-OTP Verification & Attempt Tracking
    start_otp: Mapped[str] = mapped_column(String(6), nullable=False, default="4821")
    end_otp: Mapped[str] = mapped_column(String(6), nullable=False, default="9134")
    start_otp_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_otp_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_start_otp_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_end_otp_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_otp_verified_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    end_otp_verified_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_otp_attempt_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Base Inspection Breakdown (₹239 = ₹199 Worker + ₹30 Tech/Ops + ₹10 Gullak)
    worker_payout_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=199.00)
    platform_tech_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=30.00)
    welfare_pool_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=10.00)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=239.00)

    # Additional Work Quotation & Final Amount
    additional_service_charge: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    material_charge: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    final_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=239.00)
    quotation_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="NONE")  # NONE, QUOTE_PENDING, QUOTE_APPROVED, QUOTE_REJECTED
    customer_approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    work_completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # 72-Hour Cooperative Workmanship Protection
    warranty_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warranty_started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    warranty_expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    customer: Mapped["CustomerData"] = relationship("CustomerData", back_populates="bookings")
    worker: Mapped["WorkerData"] = relationship("WorkerData", back_populates="bookings")
    service: Mapped["Service"] = relationship("Service", back_populates="bookings")
    review: Mapped[Optional["RatingReview"]] = relationship("RatingReview", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    welfare_entries: Mapped[List["CooperativeWelfareLedger"]] = relationship("CooperativeWelfareLedger", back_populates="booking")
    quotations: Mapped[List["Quotation"]] = relationship("Quotation", back_populates="booking", cascade="all, delete-orphan")
    payment_records: Mapped[List["PaymentRecord"]] = relationship("PaymentRecord", back_populates="booking", cascade="all, delete-orphan")


class Quotation(Base):
    """
    Table: quotations
    On-site additional work quotation created by worker and approved/rejected by customer.
    """
    __tablename__ = "quotations"

    quotation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.booking_id", ondelete="CASCADE"), nullable=False, index=True
    )
    worker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("worker_data.worker_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)  # DRAFT, QUOTE_PENDING, QUOTE_APPROVED, QUOTE_REJECTED
    additional_labor_charge: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    additional_material_charge: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    total_additional_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    worker_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    booking: Mapped["Booking"] = relationship("Booking", back_populates="quotations")
    worker: Mapped["WorkerData"] = relationship("WorkerData")
    items: Mapped[List["QuotationItem"]] = relationship("QuotationItem", back_populates="quotation", cascade="all, delete-orphan")


class QuotationItem(Base):
    """
    Table: quotation_items
    Line items on a quotation backed strictly by approved database RateCardItem.
    """
    __tablename__ = "quotation_items"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quotation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quotations.quotation_id", ondelete="CASCADE"), nullable=False, index=True
    )
    rate_card_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rate_card_items.item_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="LABOR")
    unit_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    quotation: Mapped["Quotation"] = relationship("Quotation", back_populates="items")
    rate_card_item: Mapped["RateCardItem"] = relationship("RateCardItem", back_populates="quotation_items")


class PaymentRecord(Base):
    """
    Table: payment_records
    Payment transaction audit log supporting Razorpay and isolated Demo Pay mode.
    """
    __tablename__ = "payment_records"

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.booking_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="DEMO_PAY")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUCCESS", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    booking: Mapped["Booking"] = relationship("Booking", back_populates="payment_records")


class CooperativeWelfareLedger(Base):
    """
    Table: cooperative_welfare_ledger
    Cooperative Welfare Ledger / Society Gullak reserve fund (Slide 3 Welfare DB).
    Tracks transparent ₹10 per booking contributions and community disbursements.
    """
    __tablename__ = "cooperative_welfare_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bookings.booking_id", ondelete="SET NULL"), nullable=True, index=True
    )
    society_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=10.00)
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False, default="CREDIT")  # CREDIT, DEBIT
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    booking: Mapped[Optional["Booking"]] = relationship("Booking", back_populates="welfare_entries")


class RatingReview(Base):
    """
    Table: ratings_reviews
    Customer feedback and ratings (1.0 to 5.0) for completed bookings with 1-to-1 constraint.
    """
    __tablename__ = "ratings_reviews"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bookings.booking_id", ondelete="CASCADE"),
        unique=True,  # 1-to-1 constraint
        nullable=False,
        index=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customer_data.customer_id", ondelete="SET NULL"), nullable=True, index=True
    )
    worker_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("worker_data.worker_id", ondelete="SET NULL"), nullable=True, index=True
    )
    rating: Mapped[float] = mapped_column(
        Numeric(2, 1),
        CheckConstraint("rating >= 1.0 AND rating <= 5.0", name="rating_range_check"),
        nullable=False
    )
    review: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, server_default=func.now())

    booking: Mapped["Booking"] = relationship("Booking", back_populates="review")
    customer: Mapped[Optional["CustomerData"]] = relationship("CustomerData", back_populates="reviews")
    worker: Mapped[Optional["WorkerData"]] = relationship("WorkerData", back_populates="reviews")
