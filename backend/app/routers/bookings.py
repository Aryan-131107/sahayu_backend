"""
routers/bookings.py — Booking Lifecycle Management & Double Booking Guard

LIFECYCLE STATE MACHINE:
  PENDING    → ACCEPTED, REJECTED, CANCELLED
  ACCEPTED   → IN_PROGRESS, CANCELLED
  IN_PROGRESS→ COMPLETED
  COMPLETED, REJECTED, CANCELLED → Terminal states
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models import Booking, WorkerData, CustomerData, Service, WorkerSkill, Availability
from app.schemas import BookingCreate, BookingResponse
from app.core.auth import get_optional_current_user, require_customer, require_worker, AuthUser

router = APIRouter(prefix="/bookings", tags=["Bookings"])

VALID_TRANSITIONS = {
    "PENDING": ["ACCEPTED", "REJECTED", "CANCELLED"],
    "ACCEPTED": ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS": ["COMPLETED"],
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


def _format_booking_response(b: Booking) -> BookingResponse:
    amount_val = float(b.amount) if b.amount is not None else 0.0
    est_price_val = float(b.estimated_price) if b.estimated_price is not None else amount_val
    lat_val = float(b.service_lat) if b.service_lat is not None else None
    lon_val = float(b.service_lon) if b.service_lon is not None else None

    return BookingResponse(
        booking_id=b.booking_id,
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
        created_at=b.created_at,
        worker_name=b.worker.name if b.worker else None,
        customer_name=b.customer.name if b.customer else None,
        service_name=b.service.service_name if b.service else None,
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
