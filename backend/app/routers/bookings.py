"""
routers/bookings.py — Booking Lifecycle Management & Double Booking Guard

LIFECYCLE STATE MACHINE:
  PENDING    → ACCEPTED, REJECTED, CANCELLED
  ACCEPTED   → IN_PROGRESS, CANCELLED
  IN_PROGRESS→ COMPLETED
  COMPLETED, REJECTED, CANCELLED → Terminal states
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models import (
    Booking, WorkerData, CustomerData, Service, WorkerSkill, Availability,
    CooperativeWelfareLedger, Skill, RateCardItem, Quotation, QuotationItem
)
from app.schemas import (
    BookingCreate, BookingResponse, BookingCreateRequest, DualOtpBookingResponse,
    BookingPricingBreakdown, VerifyStartOtpRequest, VerifyStartOtpResponse,
    VerifyEndOtpRequest, VerifyEndOtpResponse, WelfareMetricsResponse,
    RateCardItemResponse, RateCardListResponse, QuotationCreateRequest,
    QuotationResponse, QuotationItemResponse, QuotationApprovalRequest,
    QuotationRejectionRequest
)
from app.core.auth import get_optional_current_user, require_customer, require_worker, AuthUser

router = APIRouter(prefix="/bookings", tags=["Bookings"])

VALID_TRANSITIONS = {
    "PENDING": ["ACCEPTED", "IN_PROGRESS", "REJECTED", "CANCELLED"],
    "ACCEPTED": ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS": ["WORK_COMPLETED", "PAYMENT_PENDING", "COMPLETED", "CANCELLED"],
    "WORK_COMPLETED": ["PAYMENT_PENDING", "COMPLETED", "CANCELLED"],
    "PAYMENT_PENDING": ["COMPLETED", "CANCELLED"],
    "COMPLETED": [],
    "REJECTED": [],
    "CANCELLED": [],
}


def _validate_booking_transition(current: str, target: str) -> None:
    """Validate allowed state transitions according to state machine."""
    current_norm = current.upper()
    target_norm = target.upper()
    allowed = VALID_TRANSITIONS.get(current_norm, [])
    if target_norm not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot transition booking from '{current}' to '{target}'. "
                f"Allowed next states from '{current}': {allowed or 'None (Terminal state)'}."
            ),
        )


def _format_quotation_response(q: Quotation) -> QuotationResponse:
    items_resp = [
        QuotationItemResponse(
            item_id=item.item_id,
            quotation_id=item.quotation_id,
            rate_card_item_id=item.rate_card_item_id,
            item_name=item.item_name,
            category=item.category,
            unit_rate=float(item.unit_rate),
            quantity=item.quantity,
            total_amount=float(item.total_amount),
            created_at=item.created_at,
        )
        for item in (q.items or [])
    ]
    return QuotationResponse(
        quotation_id=q.quotation_id,
        booking_id=q.booking_id,
        worker_id=q.worker_id,
        status=q.status,
        additional_labor_charge=float(q.additional_labor_charge or 0.00),
        additional_material_charge=float(q.additional_material_charge or 0.00),
        total_additional_amount=float(q.total_additional_amount or 0.00),
        worker_notes=q.worker_notes,
        customer_notes=q.customer_notes,
        submitted_at=q.submitted_at,
        approved_at=q.approved_at,
        rejected_at=q.rejected_at,
        created_at=q.created_at,
        items=items_resp,
    )


def _format_booking_response(b: Booking) -> BookingResponse:
    amount_val = float(b.amount) if b.amount is not None else 0.0
    est_price_val = float(b.estimated_price) if b.estimated_price is not None else amount_val
    lat_val = float(b.service_lat) if b.service_lat is not None else None
    lon_val = float(b.service_lon) if b.service_lon is not None else None
    final_amt = float(b.final_amount) if b.final_amount is not None else float(b.total_amount or amount_val)

    latest_q = None
    if b.quotations:
        latest_q = _format_quotation_response(b.quotations[-1])

    return BookingResponse(
        booking_id=b.booking_id,
        booking_reference=f"SH-{b.booking_id:04d}",
        customer_id=b.customer_id,
        worker_id=b.worker_id,
        service_id=b.service_id,
        booking_date=b.booking_date,
        start_time=b.start_time,
        address=b.address,
        description=b.description,
        amount=amount_val,
        estimated_price=est_price_val,
        service_lat=lat_val,
        service_lon=lon_val,
        status=b.status,
        payment_status=b.payment_status,
        start_otp=b.start_otp or "4821",
        end_otp=b.end_otp or "9134",
        start_otp_attempts=b.start_otp_attempts or 0,
        end_otp_attempts=b.end_otp_attempts or 0,
        is_start_otp_locked=bool(b.is_start_otp_locked),
        is_end_otp_locked=bool(b.is_end_otp_locked),
        start_otp_verified_at=b.start_otp_verified_at,
        end_otp_verified_at=b.end_otp_verified_at,
        worker_payout_amount=float(b.worker_payout_amount) if b.worker_payout_amount is not None else 199.00,
        platform_tech_fee=float(b.platform_tech_fee) if b.platform_tech_fee is not None else 30.00,
        welfare_pool_fee=float(b.welfare_pool_fee) if b.welfare_pool_fee is not None else 10.00,
        total_amount=float(b.total_amount) if b.total_amount is not None else amount_val,
        additional_service_charge=float(b.additional_service_charge or 0.00),
        material_charge=float(b.material_charge or 0.00),
        final_amount=final_amt,
        quotation_status=b.quotation_status or "NONE",
        customer_approved_at=b.customer_approved_at,
        work_completed_at=b.work_completed_at,
        payment_reference=b.payment_reference,
        payment_completed_at=b.payment_completed_at,
        settled_at=b.settled_at,
        warranty_active=bool(b.warranty_active),
        warranty_started_at=b.warranty_started_at,
        warranty_expires_at=b.warranty_expires_at,
        created_at=b.created_at,
        worker_name=b.worker.name if b.worker else None,
        customer_name=b.customer.name if b.customer else None,
        service_name=b.service.service_name if b.service else None,
        latest_quotation=latest_q,
    )


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service booking",
)
def create_booking(
    payload: BookingCreate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new booking with comprehensive validation:
    1. Customer validation (auto-resolved from JWT if omitted)
    2. Worker validation & active check
    3. Service validation & Skill alignment check
    4. Double Booking Guard: Rejects overlapping slots for the same worker
    """
    # 1. Resolve & Validate customer
    target_customer_id = payload.customer_id
    if not target_customer_id:
        if current_user and current_user.role == "customer":
            target_customer_id = current_user.id
        else:
            raise HTTPException(status_code=400, detail="customer_id is required or user must be logged in as customer.")

    customer = db.get(CustomerData, target_customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {target_customer_id} not found.")

    if current_user and current_user.role == "customer" and current_user.id != target_customer_id:
        raise HTTPException(status_code=403, detail="Cannot create bookings on behalf of another customer.")

    # 2. Validate worker
    worker = db.get(WorkerData, payload.worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {payload.worker_id} not found.")
    if not worker.is_active:
        raise HTTPException(status_code=400, detail=f"Worker {worker.name} is currently inactive.")

    # 3. Validate service
    service = db.get(Service, payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service {payload.service_id} not found.")

    # 4. Validate worker has required skill
    has_skill = (
        db.query(WorkerSkill)
        .filter(WorkerSkill.worker_id == payload.worker_id)
        .filter(WorkerSkill.skill_id == service.skill_id)
        .first()
    )
    if not has_skill:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Worker {worker.name} does not possess the required skill for this service."
        )

    # 5. DOUBLE BOOKING GUARD: Check for conflicting bookings
    target_date = payload.booking_date or date.today()
    conflict_query = (
        db.query(Booking)
        .filter(Booking.worker_id == payload.worker_id)
        .filter(Booking.booking_date == target_date)
        .filter(Booking.status.in_(["PENDING", "ACCEPTED", "IN_PROGRESS"]))
    )
    if payload.start_time:
        conflict_query = conflict_query.filter(Booking.start_time == payload.start_time)

    overlapping_booking = conflict_query.first()
    if overlapping_booking:
        time_info = f" at {payload.start_time}" if payload.start_time else ""
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Worker {worker.name} is already booked on {target_date}{time_info}. Double booking is prohibited."
        )

    # 6. Real-time availability check if no explicit slot
    if not payload.booking_date and not payload.start_time:
        avail = db.query(Availability).filter(Availability.worker_id == payload.worker_id).first()
        if avail and not avail.is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Worker {worker.name} is currently unavailable."
            )

    # Create Booking
    booking = Booking(
        customer_id=target_customer_id,
        worker_id=payload.worker_id,
        service_id=payload.service_id,
        booking_date=target_date,
        start_time=payload.start_time,
        address=payload.address or customer.address,
        description=payload.description,
        amount=payload.amount,
        estimated_price=payload.amount,
        service_lat=payload.service_lat or customer.latitude,
        service_lon=payload.service_lon or customer.longitude,
        status="PENDING",
        payment_status="PENDING",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.get(
    "",
    response_model=List[BookingResponse],
    summary="List all bookings with optional filters",
)
def list_bookings(
    status: Optional[str] = Query(None, description="Optional status filter"),
    customer_id: Optional[int] = Query(None, description="Optional customer filter"),
    worker_id: Optional[int] = Query(None, description="Optional worker filter"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List bookings with optional status, customer, or worker filters."""
    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
    )
    if status:
        query = query.filter(func.upper(Booking.status) == status.upper())
    if customer_id:
        query = query.filter(Booking.customer_id == customer_id)
    if worker_id:
        query = query.filter(Booking.worker_id == worker_id)

    bookings = query.order_by(Booking.booking_id.desc()).limit(limit).all()
    return [_format_booking_response(b) for b in bookings]


@router.get(
    "/customer/me",
    response_model=List[BookingResponse],
    summary="Get booking history for currently logged-in customer",
)
def get_my_customer_bookings(
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    current_user: AuthUser = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Retrieve all bookings of the currently authenticated customer."""
    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
        .filter(Booking.customer_id == current_user.id)
    )
    if status_filter:
        query = query.filter(func.upper(Booking.status) == status_filter.upper())

    bookings = query.order_by(Booking.booking_id.desc()).all()
    return [_format_booking_response(b) for b in bookings]


@router.get(
    "/worker/me",
    response_model=List[BookingResponse],
    summary="Get booking feed for currently logged-in worker",
)
def get_my_worker_bookings(
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    current_user: AuthUser = Depends(require_worker),
    db: Session = Depends(get_db),
):
    """Retrieve all bookings assigned to the currently authenticated worker."""
    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
        .filter(Booking.worker_id == current_user.id)
    )
    if status_filter:
        query = query.filter(func.upper(Booking.status) == status_filter.upper())

    bookings = query.order_by(Booking.booking_id.desc()).all()
    return [_format_booking_response(b) for b in bookings]


@router.get(
    "/customer/{customer_id}",
    response_model=List[BookingResponse],
    summary="Get booking history for a customer",
)
def get_customer_bookings(
    customer_id: int,
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all bookings requested by a customer."""
    if current_user and current_user.role == "customer" and current_user.id != customer_id:
        raise HTTPException(status_code=403, detail="Cannot view another customer's booking history.")

    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
        .filter(Booking.customer_id == customer_id)
    )
    if status_filter:
        query = query.filter(func.upper(Booking.status) == status_filter.upper())

    bookings = query.order_by(Booking.booking_id.desc()).all()
    return [_format_booking_response(b) for b in bookings]


@router.get(
    "/worker/{worker_id}",
    response_model=List[BookingResponse],
    summary="Get booking feed for a worker",
)
def get_worker_bookings(
    worker_id: int,
    status_filter: Optional[str] = Query(None, description="Optional status filter"),
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all bookings assigned to a worker."""
    if current_user and current_user.role == "worker" and current_user.id != worker_id:
        raise HTTPException(status_code=403, detail="Cannot view another worker's booking feed.")

    query = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
        .filter(Booking.worker_id == worker_id)
    )
    if status_filter:
        query = query.filter(func.upper(Booking.status) == status_filter.upper())

    bookings = query.order_by(Booking.booking_id.desc()).all()
    return [_format_booking_response(b) for b in bookings]


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get single booking by ID",
)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    """Retrieve full booking details."""
    booking = (
        db.query(Booking)
        .options(
            joinedload(Booking.customer),
            joinedload(Booking.worker),
            joinedload(Booking.service),
        )
        .filter(Booking.booking_id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")
    return _format_booking_response(booking)


@router.patch(
    "/{booking_id}/accept",
    response_model=BookingResponse,
    summary="Worker accepts a pending booking",
)
def accept_booking(
    booking_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Worker accepts booking, automatically locking worker availability."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "worker" and current_user.id != booking.worker_id:
        raise HTTPException(status_code=403, detail="Cannot accept a booking assigned to another worker.")

    _validate_booking_transition(booking.status, "ACCEPTED")
    booking.status = "ACCEPTED"

    # Toggle real-time availability to busy
    avail = db.query(Availability).filter(Availability.worker_id == booking.worker_id).first()
    if avail:
        avail.is_available = False

    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.patch(
    "/{booking_id}/reject",
    response_model=BookingResponse,
    summary="Worker rejects a pending booking",
)
def reject_booking(
    booking_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Worker rejects pending booking."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "worker" and current_user.id != booking.worker_id:
        raise HTTPException(status_code=403, detail="Cannot reject a booking assigned to another worker.")

    _validate_booking_transition(booking.status, "REJECTED")
    booking.status = "REJECTED"

    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.patch(
    "/{booking_id}/start",
    response_model=BookingResponse,
    summary="Worker starts work (IN_PROGRESS)",
)
def start_booking(
    booking_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Worker starts active job execution."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "worker" and current_user.id != booking.worker_id:
        raise HTTPException(status_code=403, detail="Cannot start a booking assigned to another worker.")

    _validate_booking_transition(booking.status, "IN_PROGRESS")
    booking.status = "IN_PROGRESS"

    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.patch(
    "/{booking_id}/complete",
    response_model=BookingResponse,
    summary="Complete a booking (Marks PAID & Frees Worker)",
)
def complete_booking(
    booking_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Marks booking as completed, marks payment paid, and frees up worker availability."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "worker" and current_user.id != booking.worker_id:
        raise HTTPException(status_code=403, detail="Cannot complete a booking assigned to another worker.")

    _validate_booking_transition(booking.status, "COMPLETED")
    booking.status = "COMPLETED"
    booking.payment_status = "PAID"

    # Free up worker
    avail = db.query(Availability).filter(Availability.worker_id == booking.worker_id).first()
    if avail:
        avail.is_available = True

    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.patch(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
)
def cancel_booking(
    booking_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Cancels PENDING or ACCEPTED booking. Frees worker if was accepted."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user:
        if current_user.role == "customer" and current_user.id != booking.customer_id:
            raise HTTPException(status_code=403, detail="Cannot cancel another customer's booking.")
        if current_user.role == "worker" and current_user.id != booking.worker_id:
            raise HTTPException(status_code=403, detail="Cannot cancel another worker's booking.")

    _validate_booking_transition(booking.status, "CANCELLED")
    was_accepted = booking.status == "ACCEPTED"
    booking.status = "CANCELLED"

    if was_accepted:
        avail = db.query(Availability).filter(Availability.worker_id == booking.worker_id).first()
        if avail:
            avail.is_available = True

    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


# ─────────────────────────────────────────────────────────
# RATE CARD & ON-SITE QUOTATION ENDPOINTS
# ─────────────────────────────────────────────────────────

@router.get(
    "/rate-card",
    response_model=RateCardListResponse,
    summary="Get rate card items by skill ID",
)
def get_rate_card_by_skill(
    skill_id: int = Query(..., description="Skill ID to fetch rate card for"),
    db: Session = Depends(get_db),
):
    skill = db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found.")

    items = (
        db.query(RateCardItem)
        .filter(RateCardItem.skill_id == skill_id, RateCardItem.is_active == True)
        .order_by(RateCardItem.category, RateCardItem.item_name)
        .all()
    )

    return RateCardListResponse(
        skill_id=skill_id,
        skill_name=skill.skill_name,
        items=[
            RateCardItemResponse(
                item_id=it.item_id,
                skill_id=it.skill_id,
                service_id=it.service_id,
                item_name=it.item_name,
                category=it.category,
                unit_rate=float(it.unit_rate),
                unit=it.unit,
                description=it.description,
                is_active=it.is_active,
            )
            for it in items
        ],
    )


@router.get(
    "/{booking_id}/rate-card",
    response_model=RateCardListResponse,
    summary="Get trade-specific rate card items for a booking",
)
def get_booking_rate_card(
    booking_id: int,
    db: Session = Depends(get_db),
):
    """
    Fetches strictly the trade-specific rate card items belonging to the booking's skill.
    Prevents skill-card mismatch (e.g. Painting job never sees MCB/Capacitor).
    """
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    service = booking.service or db.get(Service, booking.service_id)
    skill_id = service.skill_id if service else 1
    skill = db.get(Skill, skill_id)

    items = (
        db.query(RateCardItem)
        .filter(RateCardItem.skill_id == skill_id, RateCardItem.is_active == True)
        .order_by(RateCardItem.category, RateCardItem.item_name)
        .all()
    )

    return RateCardListResponse(
        skill_id=skill_id,
        skill_name=skill.skill_name if skill else None,
        service_id=service.service_id if service else None,
        service_name=service.service_name if service else None,
        items=[
            RateCardItemResponse(
                item_id=it.item_id,
                skill_id=it.skill_id,
                service_id=it.service_id,
                item_name=it.item_name,
                category=it.category,
                unit_rate=float(it.unit_rate),
                unit=it.unit,
                description=it.description,
                is_active=it.is_active,
            )
            for it in items
        ],
    )


@router.post(
    "/{booking_id}/quotation",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Worker submits on-site quotation for additional labor and parts",
)
def create_quotation(
    booking_id: int,
    payload: QuotationCreateRequest,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Worker submits on-site quotation:
    - Validates items belong to booking's skill category (rejects cross-trade items)
    - Authoritative database pricing (rejects arbitrary frontend prices)
    - Sets quotation to QUOTE_PENDING
    """
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "worker" and current_user.id != booking.worker_id:
        raise HTTPException(status_code=403, detail="Cannot submit quotation for a booking assigned to another worker.")

    service = booking.service or db.get(Service, booking.service_id)
    skill_id = service.skill_id if service else 1

    if not payload.items:
        raise HTTPException(status_code=400, detail="Quotation must contain at least one item.")

    labor_total = Decimal("0.00")
    material_total = Decimal("0.00")
    validated_items = []

    for item_req in payload.items:
        rc_item = db.get(RateCardItem, item_req.rate_card_item_id)
        if not rc_item or not rc_item.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rate card item {item_req.rate_card_item_id} not found or inactive.",
            )
        if rc_item.skill_id != skill_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Rate card item '{rc_item.item_name}' belongs to skill ID {rc_item.skill_id}, "
                    f"which does not match booking trade skill ID {skill_id}."
                ),
            )
        qty = max(1, item_req.quantity)
        amt = Decimal(str(rc_item.unit_rate)) * qty
        if rc_item.category.upper() == "LABOR":
            labor_total += amt
        else:
            material_total += amt
        validated_items.append((rc_item, qty, float(amt)))

    total_add = labor_total + material_total
    now = datetime.now()

    quote = Quotation(
        booking_id=booking_id,
        worker_id=booking.worker_id,
        status="QUOTE_PENDING",
        additional_labor_charge=float(labor_total),
        additional_material_charge=float(material_total),
        total_additional_amount=float(total_add),
        worker_notes=payload.worker_notes,
        submitted_at=now,
    )
    db.add(quote)
    db.flush()

    for rc_item, qty, amt in validated_items:
        qi = QuotationItem(
            quotation_id=quote.quotation_id,
            rate_card_item_id=rc_item.item_id,
            item_name=rc_item.item_name,
            category=rc_item.category,
            unit_rate=float(rc_item.unit_rate),
            quantity=qty,
            total_amount=amt,
        )
        db.add(qi)

    booking.quotation_status = "QUOTE_PENDING"
    db.commit()
    db.refresh(quote)
    return _format_quotation_response(quote)


@router.get(
    "/{booking_id}/quotation",
    response_model=Optional[QuotationResponse],
    summary="Get latest quotation for a booking",
)
def get_booking_quotation(
    booking_id: int,
    db: Session = Depends(get_db),
):
    quote = (
        db.query(Quotation)
        .filter(Quotation.booking_id == booking_id)
        .order_by(Quotation.quotation_id.desc())
        .first()
    )
    if not quote:
        return None
    return _format_quotation_response(quote)


@router.post(
    "/{booking_id}/quotation/approve",
    response_model=BookingResponse,
    summary="Customer approves quotation",
)
def approve_quotation(
    booking_id: int,
    payload: Optional[QuotationApprovalRequest] = None,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "customer" and current_user.id != booking.customer_id:
        raise HTTPException(status_code=403, detail="Cannot approve quotation for another customer's booking.")

    quote = (
        db.query(Quotation)
        .filter(Quotation.booking_id == booking_id, Quotation.status == "QUOTE_PENDING")
        .order_by(Quotation.quotation_id.desc())
        .first()
    )
    if not quote:
        raise HTTPException(status_code=404, detail="No pending quotation found for this booking.")

    now = datetime.now()
    quote.status = "QUOTE_APPROVED"
    quote.approved_at = now
    if payload and payload.customer_notes:
        quote.customer_notes = payload.customer_notes

    # Update booking with approved quotation amounts
    base_charge = 239.00
    total_additional = float(quote.total_additional_amount)
    final_total = round(base_charge + total_additional, 2)

    booking.quotation_status = "QUOTE_APPROVED"
    booking.customer_approved_at = now
    booking.additional_service_charge = float(quote.additional_labor_charge)
    booking.material_charge = float(quote.additional_material_charge)
    booking.final_amount = final_total
    booking.total_amount = final_total
    booking.worker_payout_amount = round(199.00 + float(quote.additional_labor_charge) + float(quote.additional_material_charge), 2)

    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.post(
    "/{booking_id}/quotation/reject",
    response_model=BookingResponse,
    summary="Customer rejects quotation",
)
def reject_quotation(
    booking_id: int,
    payload: Optional[QuotationRejectionRequest] = None,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "customer" and current_user.id != booking.customer_id:
        raise HTTPException(status_code=403, detail="Cannot reject quotation for another customer's booking.")

    quote = (
        db.query(Quotation)
        .filter(Quotation.booking_id == booking_id, Quotation.status == "QUOTE_PENDING")
        .order_by(Quotation.quotation_id.desc())
        .first()
    )
    if not quote:
        raise HTTPException(status_code=404, detail="No pending quotation found for this booking.")

    now = datetime.now()
    quote.status = "QUOTE_REJECTED"
    quote.rejected_at = now
    if payload and payload.customer_notes:
        quote.customer_notes = payload.customer_notes

    booking.quotation_status = "QUOTE_REJECTED"
    booking.additional_service_charge = 0.00
    booking.material_charge = 0.00
    booking.final_amount = 239.00
    booking.total_amount = 239.00
    booking.worker_payout_amount = 199.00

    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.post(
    "/{booking_id}/work-completed",
    response_model=BookingResponse,
    summary="Worker marks work complete before Completion OTP",
)
@router.patch(
    "/{booking_id}/work-completed",
    response_model=BookingResponse,
    summary="Worker marks work complete before Completion OTP",
)
def mark_work_completed(
    booking_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    if current_user and current_user.role == "worker" and current_user.id != booking.worker_id:
        raise HTTPException(status_code=403, detail="Cannot mark work complete for a booking assigned to another worker.")

    now = datetime.now()
    booking.work_completed_at = now
    booking.status = "WORK_COMPLETED"
    db.commit()
    db.refresh(booking)
    return _format_booking_response(booking)


@router.post(
    "/{booking_id}/verify-start",
    response_model=VerifyStartOtpResponse,
    summary="Validate Start PIN (4821) by booking ID URL param",
)
def verify_start_by_id(
    booking_id: int,
    payload: VerifyStartOtpRequest,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    payload.booking_id = booking_id
    return verify_start_otp(payload, current_user, db)


@router.post(
    "/{booking_id}/verify-end",
    response_model=VerifyEndOtpResponse,
    summary="Validate End PIN (9134) by booking ID URL param",
)
def verify_end_by_id(
    booking_id: int,
    payload: VerifyEndOtpRequest,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    payload.booking_id = booking_id
    return verify_end_otp(payload, current_user, db)


# ─────────────────────────────────────────────────────────
# DUAL-OTP STATE MACHINE & WELFARE DB ENDPOINTS (Slide 3)
# ─────────────────────────────────────────────────────────

@router.post(
    "/create",
    response_model=DualOtpBookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize booking with Dual-OTP locks and Slide 3 Transparent Pricing",
)
def create_dual_otp_booking(
    payload: BookingCreateRequest,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Initializes a new booking adhering to Slide 3 core business logic:
    - Sets status to 'pending'
    - Locks Start PIN to '4821' and End PIN to '9134' (demo predictability)
    - Transparent pricing: ₹199 worker payout, ₹30 platform tech fee, ₹10 society gullak, total ₹239
    - Returns booking reference (e.g. 'SH-0060') and pricing breakdown
    """
    # 1. Resolve customer
    target_customer_id = payload.customer_id
    if not target_customer_id:
        if current_user and current_user.role == "customer":
            target_customer_id = current_user.id
        else:
            first_cust = db.query(CustomerData).first()
            target_customer_id = first_cust.customer_id if first_cust else 1

    customer = db.get(CustomerData, target_customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {target_customer_id} not found.")

    # 2. Validate worker
    worker = db.get(WorkerData, payload.worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {payload.worker_id} not found.")

    # 3. Resolve service
    service_id = payload.service_id or 1
    service = db.get(Service, service_id)
    if not service:
        first_svc = db.query(Service).first()
        service = first_svc
        service_id = first_svc.service_id if first_svc else 1

    # 4. Create booking with Dual-OTP & Slide 3 pricing parameters
    booking = Booking(
        customer_id=target_customer_id,
        worker_id=payload.worker_id,
        service_id=service_id,
        booking_date=payload.booking_date or date.today(),
        start_time=payload.start_time or time(10, 0),
        address=payload.location or "Civil Lines, Jabalpur",
        description=payload.service_scope or "Electrical Inspection & Fault Diagnosis",
        estimated_price=239.00,
        amount=239.00,
        status="pending",
        payment_status="PENDING",
        start_otp="4821",
        end_otp="9134",
        worker_payout_amount=199.00,
        platform_tech_fee=30.00,
        welfare_pool_fee=10.00,
        total_amount=239.00,
        final_amount=239.00,
        quotation_status="NONE",
        warranty_active=False,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    ref = f"SH-{booking.booking_id:04d}"

    pricing = BookingPricingBreakdown(
        worker_payout=199.00,
        platform_tech_fee=30.00,
        welfare_pool_fee=10.00,
        total_amount=239.00,
        currency="INR",
    )

    return DualOtpBookingResponse(
        booking_id=booking.booking_id,
        booking_reference=ref,
        status="pending",
        customer_id=booking.customer_id,
        worker_id=booking.worker_id,
        service_scope=payload.service_scope or "Electrical Inspection & Fault Diagnosis",
        location=payload.location or "Civil Lines, Jabalpur",
        start_otp="4821",
        end_otp="9134",
        pricing=pricing,
        warranty_active=False,
        created_at=booking.created_at,
        worker_name=worker.name,
        customer_name=customer.name,
        message=f"Booking {ref} created successfully. Start PIN locked to 4821.",
    )


@router.post(
    "/verify-start-otp",
    response_model=VerifyStartOtpResponse,
    summary="Validate Start PIN (4821) and transition booking to in_progress",
)
def verify_start_otp(
    payload: VerifyStartOtpRequest,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, payload.booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {payload.booking_id} not found.")

    # Authorization check
    if current_user:
        if current_user.role == "customer" and current_user.id != booking.customer_id:
            raise HTTPException(status_code=403, detail="Cannot verify Start OTP for another customer's booking.")
        if current_user.role == "worker" and current_user.id != booking.worker_id:
            raise HTTPException(status_code=403, detail="Cannot verify Start OTP for a booking assigned to another worker.")

    # State validation & Reuse protection
    status_upper = (booking.status or "").upper()
    if status_upper in ["IN_PROGRESS", "WORK_COMPLETED", "PAYMENT_PENDING", "COMPLETED"] or booking.start_otp_verified_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot verify Start OTP. Booking is already '{booking.status}' (Start OTP cannot be reused).",
        )
    if status_upper in ["CANCELLED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot verify Start OTP on a '{booking.status}' booking.",
        )

    # Attempt limit & Lock check
    if booking.is_start_otp_locked or (booking.start_otp_attempts or 0) >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts reached (3/3). Start PIN verification is locked.",
        )

    otp_clean = payload.otp.strip()
    expected_otp = (booking.start_otp or "4821").strip()
    now = datetime.now()

    # Validate PIN
    if otp_clean != expected_otp and otp_clean != "4821":
        booking.start_otp_attempts = (booking.start_otp_attempts or 0) + 1
        booking.last_otp_attempt_at = now
        if booking.start_otp_attempts >= 3:
            booking.is_start_otp_locked = True
        db.commit()

        attempts_remaining = max(0, 3 - booking.start_otp_attempts)
        if booking.start_otp_attempts >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts reached (3/3). Start PIN verification is locked.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Handshake PIN. Attempt {booking.start_otp_attempts} of 3 recorded. {attempts_remaining} attempts remaining.",
            )

    # Success Flow
    booking.start_otp_verified_at = now
    booking.status = "in_progress"
    db.commit()
    db.refresh(booking)

    ref = f"SH-{booking.booking_id:04d}"
    return VerifyStartOtpResponse(
        success=True,
        booking_id=booking.booking_id,
        booking_reference=ref,
        status="in_progress",
        message="Doorstep arrival verified. Work is now in progress.",
        arrival_confirmed=True,
        verification_timestamp=now,
        start_time=now,
        transaction_id=f"TXN-START-{booking.booking_id:06d}",
    )


@router.post(
    "/verify-end-otp",
    response_model=VerifyEndOtpResponse,
    summary="Validate End PIN (9134) and transition to PAYMENT_PENDING",
)
def verify_end_otp(
    payload: VerifyEndOtpRequest,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Validates End PIN ('9134') and transitions booking to PAYMENT_PENDING:
    - Verifies booking exists and user authorization
    - Validates booking is in IN_PROGRESS or WORK_COMPLETED state
    - Rejects duplicate verification if booking is already COMPLETED / PAID
    - Enforces max 3 attempts limit and server-side lock
    - On success: transitions to 'payment_pending' awaiting customer payment to settle and activate warranty
    """
    booking = db.get(Booking, payload.booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {payload.booking_id} not found.")

    # Authorization check
    if current_user:
        if current_user.role == "customer" and current_user.id != booking.customer_id:
            raise HTTPException(status_code=403, detail="Cannot verify End OTP for another customer's booking.")
        if current_user.role == "worker" and current_user.id != booking.worker_id:
            raise HTTPException(status_code=403, detail="Cannot verify End OTP for a booking assigned to another worker.")

    # State validation & Reuse protection
    status_upper = (booking.status or "").upper()
    if status_upper in ["COMPLETED"] or booking.end_otp_verified_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking is already completed. End OTP cannot be reused.",
        )
    if status_upper not in ["IN_PROGRESS", "WORK_COMPLETED", "ACCEPTED"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot verify End OTP on booking in '{booking.status}' state. Start OTP must be verified first.",
        )

    # Attempt limit & Lock check
    if booking.is_end_otp_locked or (booking.end_otp_attempts or 0) >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts reached (3/3). End PIN verification is locked.",
        )

    otp_clean = payload.otp.strip()
    expected_otp = (booking.end_otp or "9134").strip()
    now = datetime.now()

    # Validate PIN
    if otp_clean != expected_otp and otp_clean != "9134":
        booking.end_otp_attempts = (booking.end_otp_attempts or 0) + 1
        booking.last_otp_attempt_at = now
        if booking.end_otp_attempts >= 3:
            booking.is_end_otp_locked = True
        db.commit()

        attempts_remaining = max(0, 3 - booking.end_otp_attempts)
        if booking.end_otp_attempts >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts reached (3/3). End PIN verification is locked.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Completion PIN. Attempt {booking.end_otp_attempts} of 3 recorded. {attempts_remaining} attempts remaining.",
            )

    # Transition to PAYMENT_PENDING (Payment collected after completion)
    booking.end_otp_verified_at = now
    booking.status = "payment_pending"
    db.commit()
    db.refresh(booking)

    ref = f"SH-{booking.booking_id:04d}"
    total_amt = float(booking.final_amount or booking.total_amount or 239.00)
    welfare_fee = round(float(booking.welfare_pool_fee or 10.00), 2)
    worker_payout = float(booking.worker_payout_amount or (total_amt - 30.00 - welfare_fee))

    settlement = {
        "worker_payout_amount": worker_payout,
        "welfare_pool_fee": welfare_fee,
        "platform_tech_fee": float(booking.platform_tech_fee or 30.00),
        "total_settled": total_amt,
        "currency": "INR",
    }

    return VerifyEndOtpResponse(
        success=True,
        booking_id=booking.booking_id,
        booking_reference=ref,
        status="payment_pending",
        message="Completion OTP verified. Payment is now pending to finalize settlement and activate 72h warranty.",
        completion_timestamp=now,
        transaction_id=f"TXN-SAHAYU-{booking.booking_id:06d}",
        settlement_summary=settlement,
        settlement_information=settlement,
        warranty_active=False,
    )


@router.get(
    "/welfare-fund/summary",
    response_model=WelfareMetricsResponse,
    summary="Get Society Welfare Gullak Reserve Fund Summary (Slide 3 Welfare DB)",
)
def get_welfare_fund_summary(
    society_id: int = Query(1, description="Cooperative Society ID"),
    db: Session = Depends(get_db),
):
    """
    Queries cooperative_welfare_ledger for the specified society.
    Aggregates total reserve balance (CREDIT - DEBIT) and count of contributions.
    """
    credit_sum = (
        db.query(func.coalesce(func.sum(CooperativeWelfareLedger.amount), 0.0))
        .filter(
            CooperativeWelfareLedger.society_id == society_id,
            CooperativeWelfareLedger.entry_type == "CREDIT"
        )
        .scalar()
    )
    debit_sum = (
        db.query(func.coalesce(func.sum(CooperativeWelfareLedger.amount), 0.0))
        .filter(
            CooperativeWelfareLedger.society_id == society_id,
            CooperativeWelfareLedger.entry_type == "DEBIT"
        )
        .scalar()
    )
    total_balance = float(credit_sum) - float(debit_sum)

    contributions_count = (
        db.query(CooperativeWelfareLedger)
        .filter(
            CooperativeWelfareLedger.society_id == society_id,
            CooperativeWelfareLedger.entry_type == "CREDIT"
        )
        .count()
    )

    return WelfareMetricsResponse(
        society_id=society_id,
        total_gullak_reserve=round(total_balance, 2),
        total_contributions_count=contributions_count,
        governing_body="Jabalpur District Cooperative Federation",
        currency="INR",
        last_updated=datetime.now(),
    )
