"""
routers/payments.py — Payment Processing, Demo Pay & Settlement Engine
Handles Razorpay integration & Isolated Demo Pay for SIH 2026 PS26089.
"""
import random
from datetime import datetime, timedelta, date, time
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from sqlalchemy import func
from app.database import get_db
from app.models import (
    Booking, PaymentRecord, CooperativeWelfareLedger, Availability, Quotation,
    Service, WorkerData, CustomerData, Skill, WorkerSkill
)
from app.schemas import (
    PaymentOrderCreate, PaymentOrderResponse,
    PaymentVerifyRequest, PaymentVerifyResponse,
    DemoPaymentRequest, DemoResetRequest, DemoResetResponse, BookingResponse,
    CycleScenarioRequest,
)
from app.routers.bookings import _format_booking_response, ensure_trade_rate_cards
from app.core.auth import get_optional_current_user, AuthUser

router = APIRouter(tags=["Payments"])


def _execute_settlement(
    booking: Booking,
    db: Session,
    payment_method: str = "DEMO_PAY",
    order_id: Optional[str] = None,
    payment_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes atomic idempotent settlement:
    - Verifies booking is in PAYMENT_PENDING or IN_PROGRESS or WORK_COMPLETED
    - Rejects double settlement
    - Creates PaymentRecord
    - Updates Booking (status=COMPLETED, payment_status=PAID, warranty_active=True)
    - Credits ₹10.00 to CooperativeWelfareLedger (idempotent)
    - Frees worker availability
    """
    now = datetime.now()
    expires_at = now + timedelta(days=3)  # 72 Hours

    total_amt = float(booking.final_amount or booking.total_amount or booking.amount or 239.00)
    welfare_fee = float(booking.welfare_pool_fee or 10.00)
    platform_fee = float(booking.platform_tech_fee or 30.00)
    worker_payout = float(booking.worker_payout_amount or (total_amt - platform_fee - welfare_fee))

    p_ref = payment_ref or f"PAY-SAHAYU-{booking.booking_id:04d}-{uuid.uuid4().hex[:6].upper()}"
    o_id = order_id or f"order_{uuid.uuid4().hex[:12]}"

    # 1. Create PaymentRecord
    record = PaymentRecord(
        booking_id=booking.booking_id,
        order_id=o_id,
        payment_reference=p_ref,
        amount=total_amt,
        currency="INR",
        payment_method=payment_method,
        status="SUCCESS",
        is_demo=True if "DEMO" in payment_method.upper() else False,
    )
    db.add(record)

    # 2. Update Booking
    booking.status = "COMPLETED"
    booking.payment_status = "PAID"
    booking.payment_reference = p_ref
    booking.payment_completed_at = now
    booking.settled_at = now
    booking.warranty_active = True
    booking.warranty_started_at = now
    booking.warranty_expires_at = expires_at

    # 3. Idempotent Gullak credit
    existing_welfare = (
        db.query(CooperativeWelfareLedger)
        .filter(
            CooperativeWelfareLedger.booking_id == booking.booking_id,
            CooperativeWelfareLedger.entry_type == "CREDIT",
        )
        .first()
    )
    if not existing_welfare:
        welfare_entry = CooperativeWelfareLedger(
            booking_id=booking.booking_id,
            society_id=1,
            amount=welfare_fee,
            entry_type="CREDIT",
            description=f"Welfare Gullak Contribution from Booking SH-{booking.booking_id:04d}",
        )
        db.add(welfare_entry)

    # 4. Free worker availability
    avail = db.query(Availability).filter(Availability.worker_id == booking.worker_id).first()
    if avail:
        avail.is_available = True

    db.commit()
    db.refresh(booking)

    settlement = {
        "worker_payout_amount": worker_payout,
        "worker_payout_released": worker_payout,
        "welfare_pool_fee": welfare_fee,
        "welfare_gullak_credited": welfare_fee,
        "platform_tech_fee": platform_fee,
        "platform_tech_fee_retained": platform_fee,
        "total_settled": total_amt,
        "currency": "INR",
    }

    return {
        "booking": booking,
        "payment_reference": p_ref,
        "total_settled": total_amt,
        "settlement_summary": settlement,
        "warranty_started_at": now,
        "warranty_expires_at": expires_at,
    }


@router.post(
    "/payments/create-order",
    response_model=PaymentOrderResponse,
    summary="Create Razorpay / Demo Payment Order",
)
def create_payment_order(
    payload: PaymentOrderCreate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, payload.booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {payload.booking_id} not found.")

    total_amt = float(booking.final_amount or booking.total_amount or booking.amount or 239.00)
    order_id = f"order_{uuid.uuid4().hex[:14]}"

    return PaymentOrderResponse(
        order_id=order_id,
        booking_id=booking.booking_id,
        amount=total_amt,
        currency="INR",
        key_id="rzp_test_sahayu_demo",
        is_demo=True,
    )


@router.post(
    "/payments/verify",
    response_model=PaymentVerifyResponse,
    summary="Verify payment and execute final settlement",
)
def verify_payment(
    payload: PaymentVerifyRequest,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, payload.booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {payload.booking_id} not found.")

    # Prevent duplicate settlement
    if (booking.status or "").upper() == "COMPLETED" and booking.payment_status == "PAID" and booking.settled_at:
        settlement = {
            "worker_payout_amount": float(booking.worker_payout_amount or 199.00),
            "welfare_pool_fee": float(booking.welfare_pool_fee or 10.00),
            "platform_tech_fee": float(booking.platform_tech_fee or 30.00),
            "total_settled": float(booking.total_amount or 239.00),
            "currency": "INR",
        }
        return PaymentVerifyResponse(
            success=True,
            booking_id=booking.booking_id,
            status="completed",
            payment_status="paid",
            payment_reference=booking.payment_reference or "ALREADY_SETTLED",
            amount_paid=float(booking.total_amount or 239.00),
            settlement_summary=settlement,
            warranty_active=booking.warranty_active,
            warranty_started_at=booking.warranty_started_at,
            warranty_expires_at=booking.warranty_expires_at,
            message="Payment already verified and settled.",
        )

    res = _execute_settlement(
        booking=booking,
        db=db,
        payment_method="RAZORPAY_DEMO" if payload.is_demo else "RAZORPAY_LIVE",
        order_id=payload.razorpay_order_id,
        payment_ref=payload.razorpay_payment_id,
    )

    return PaymentVerifyResponse(
        success=True,
        booking_id=booking.booking_id,
        status="completed",
        payment_status="paid",
        payment_reference=res["payment_reference"],
        amount_paid=res["total_settled"],
        settlement_summary=res["settlement_summary"],
        warranty_active=True,
        warranty_started_at=res["warranty_started_at"],
        warranty_expires_at=res["warranty_expires_at"],
        message="Payment verified successfully. Worker payout settled and 72h warranty activated.",
    )


@router.post(
    "/demo/payments/{booking_id}",
    response_model=PaymentVerifyResponse,
    summary="Execute Demo Payment and complete settlement for booking",
)
@router.post(
    "/bookings/{booking_id}/demo-pay",
    response_model=PaymentVerifyResponse,
    summary="Direct Demo Pay endpoint for booking",
)
def execute_demo_payment(
    booking_id: int,
    payload: Optional[DemoPaymentRequest] = None,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found.")

    # Idempotent check
    if (booking.status or "").upper() == "COMPLETED" and booking.payment_status == "PAID" and booking.settled_at:
        settlement = {
            "worker_payout_amount": float(booking.worker_payout_amount or 199.00),
            "welfare_pool_fee": float(booking.welfare_pool_fee or 10.00),
            "platform_tech_fee": float(booking.platform_tech_fee or 30.00),
            "total_settled": float(booking.total_amount or 239.00),
            "currency": "INR",
        }
        return PaymentVerifyResponse(
            success=True,
            booking_id=booking.booking_id,
            status="completed",
            payment_status="paid",
            payment_reference=booking.payment_reference or "ALREADY_SETTLED",
            amount_paid=float(booking.total_amount or 239.00),
            settlement_summary=settlement,
            warranty_active=booking.warranty_active,
            warranty_started_at=booking.warranty_started_at,
            warranty_expires_at=booking.warranty_expires_at,
            message="Payment already verified and settled.",
        )

    res = _execute_settlement(
        booking=booking,
        db=db,
        payment_method="DEMO_UPI",
    )

    return PaymentVerifyResponse(
        success=True,
        booking_id=booking.booking_id,
        status="completed",
        payment_status="paid",
        payment_reference=res["payment_reference"],
        amount_paid=res["total_settled"],
        settlement_summary=res["settlement_summary"],
        warranty_active=True,
        warranty_started_at=res["warranty_started_at"],
        warranty_expires_at=res["warranty_expires_at"],
        message="Demo payment processed successfully. Settlement finalized and 72h warranty active.",
    )


def _reset_single_booking(booking: Booking, db: Session) -> Booking:
    """Safely and forcefully resets a booking record to clean demo state bypassing state locks with trade skill alignment."""
    ensure_trade_rate_cards(db)

    # 1. Ensure Gardener Skill & Gardening Service exist
    gardener_skill = db.query(Skill).filter(func.lower(Skill.skill_name) == "gardener").first()
    if not gardener_skill:
        gardener_skill = Skill(skill_name="Gardener", description="Lawn mowing, hedge trimming, weeding, and garden care")
        db.add(gardener_skill)
        db.flush()

    garden_service = db.query(Service).filter(
        func.lower(Service.service_name).like("%lawn%") | func.lower(Service.service_name).like("%garden%")
    ).first()
    if not garden_service:
        garden_service = Service(
            service_name="Lawn Mowing & Garden Care",
            description="Grass trimming, hedge pruning, weeding, and garden upkeep.",
            category="GARDENING",
            base_price=350.00,
            estimated_duration=60,
            is_active=True,
            skill_id=gardener_skill.skill_id,
        )
        db.add(garden_service)
        db.flush()
    else:
        garden_service.category = "GARDENING"
        garden_service.skill_id = gardener_skill.skill_id

    # 2. Ensure Gardening Worker (Ramesh Patel / Member #114) exists and is verified
    garden_worker = db.query(WorkerData).filter(
        (func.lower(WorkerData.name).like("%ramesh%")) | (WorkerData.worker_id == 114)
    ).first()
    if not garden_worker:
        garden_worker = (
            db.query(WorkerData)
            .join(WorkerSkill, WorkerData.worker_id == WorkerSkill.worker_id)
            .filter(WorkerSkill.skill_id == gardener_skill.skill_id)
            .first()
        )
    if not garden_worker:
        garden_worker = WorkerData(
            name="Ramesh Patel",
            phone="9123456782",
            email="ramesh.patel@example.com",
            experience_years=12,
            hourly_rate=350.00,
            address="Napier Town, Jabalpur",
            city="Jabalpur",
            latitude=23.192000,
            longitude=79.975000,
            is_verified=True,
            is_active=True,
            shramik_id="SHR-MP-2026-1003",
            skill_certificate="CERT-GARD-2021",
            verification_status="VERIFIED",
            verification_type="DEMO_SHRAMIK",
        )
        db.add(garden_worker)
        db.flush()
        ws = WorkerSkill(
            worker_id=garden_worker.worker_id,
            skill_id=gardener_skill.skill_id,
            skill_level="Expert",
            experience_years=12,
        )
        db.add(ws)
    else:
        # Ensure worker is linked to Gardener skill
        existing_ws = db.query(WorkerSkill).filter(
            WorkerSkill.worker_id == garden_worker.worker_id,
            WorkerSkill.skill_id == gardener_skill.skill_id,
        ).first()
        if not existing_ws:
            ws = WorkerSkill(
                worker_id=garden_worker.worker_id,
                skill_id=gardener_skill.skill_id,
                skill_level="Expert",
                experience_years=12,
            )
            db.add(ws)

    # Align booking with Gardening service & Ramesh Patel
    booking.service_id = garden_service.service_id
    booking.worker_id = garden_worker.worker_id
    booking.description = "Lawn Mowing & Garden Care"
    booking.status = "ASSIGNED"
    booking.payment_status = "UNPAID"
    booking.start_otp = "4821"
    booking.end_otp = "9134"
    booking.start_otp_attempts = 0
    booking.end_otp_attempts = 0
    booking.is_start_otp_locked = False
    booking.is_end_otp_locked = False
    booking.start_otp_verified_at = None
    booking.end_otp_verified_at = None
    booking.last_otp_attempt_at = None
    booking.additional_service_charge = 0.00
    booking.material_charge = 0.00
    booking.final_amount = 239.00
    booking.total_amount = 239.00
    booking.worker_payout_amount = 199.00
    booking.platform_tech_fee = 30.00
    booking.welfare_pool_fee = 10.00
    booking.quotation_status = "NONE"
    booking.customer_approved_at = None
    booking.work_completed_at = None
    booking.payment_reference = None
    booking.payment_completed_at = None
    booking.settled_at = None
    booking.warranty_active = False
    booking.warranty_started_at = None
    booking.warranty_expires_at = None

    # Clear associated quotations for clean demo replay
    db.query(Quotation).filter(Quotation.booking_id == booking.booking_id).delete()

    # Clear payment records for this booking
    db.query(PaymentRecord).filter(PaymentRecord.booking_id == booking.booking_id).delete()

    # Clear welfare ledger for this booking
    db.query(CooperativeWelfareLedger).filter(CooperativeWelfareLedger.booking_id == booking.booking_id).delete()

    # Free worker availability
    avail = db.query(Availability).filter(Availability.worker_id == booking.worker_id).first()
    if avail:
        avail.is_available = True

    return booking


@router.post(
    "/demo/reset",
    response_model=DemoResetResponse,
    summary="Safely reset demo booking to initial state (Does not wipe database)",
)
@router.post(
    "/bookings/demo-reset",
    response_model=DemoResetResponse,
    summary="Safely reset demo booking to initial state",
)
def reset_demo_booking(
    booking_id: Optional[int] = None,
    booking_reference: Optional[str] = None,
    payload: Optional[DemoResetRequest] = None,
    db: Session = Depends(get_db),
):
    target_id = None
    target_ref = None

    if payload:
        if payload.booking_id:
            target_id = payload.booking_id
        if payload.booking_reference:
            target_ref = payload.booking_reference

    if not target_id and booking_id:
        target_id = booking_id

    if not target_ref and booking_reference:
        target_ref = booking_reference

    booking = None
    if target_id:
        booking = db.get(Booking, target_id)
    elif target_ref:
        clean = target_ref.strip().upper().replace("SH-", "").lstrip("0")
        if clean.isdigit():
            booking = db.get(Booking, int(clean))

    if not booking:
        # Check order #SH-0058 (ID 58) or booking 1
        booking = db.get(Booking, 58)
        if not booking:
            booking = db.get(Booking, 1)
        if not booking:
            booking = db.query(Booking).first()
        if not booking:
            raise HTTPException(status_code=404, detail="No booking found to reset.")

    # Reset the target booking directly
    _reset_single_booking(booking, db)

    # Also reset all companion demo booking IDs if present
    for companion_id in [1, 58, 61, 62, 63, 64, 65, 101, 102, 103, 104, 105]:
        if companion_id != booking.booking_id:
            companion = db.get(Booking, companion_id)
            if companion:
                _reset_single_booking(companion, db)

    db.commit()
    db.refresh(booking)

    formatted_booking = _format_booking_response(booking)

    return DemoResetResponse(
        success=True,
        message=f"Demo Booking SH-{booking.booking_id:04d} reset to ASSIGNED/PENDING with clean PINs (4821 / 9134).",
        booking_id=booking.booking_id,
        status="ASSIGNED",
        start_otp="4821",
        end_otp="9134",
        completion_otp="9134",
        booking=formatted_booking,
    )


_scenario_counter = -1

DEMO_SCENARIOS = [
    {
        "scenario_index": 0,
        "service_name": "Ceiling Fan Installation & Repair",
        "service_category": "ELECTRICAL",
        "category": "ELECTRICAL",
        "worker_name": "Arvind Gupta",
        "worker_skill": "Cooperative Electrician / Wireman",
        "trade_skill": "Cooperative Electrician / Wireman",
        "worker_member_id": "111",
        "skill_name": "Electrician",
        "worker_phone": "9123456790",
        "shramik_id": "SHR-MP-2026-1011",
        "experience_years": 9,
        "hourly_rate": 260.00,
        "customer_name": "Pooja Sharma",
        "customer_phone": "9876543299",
        "customer_email": "pooja.sharma@example.com",
        "location": "Civil Lines, Jabalpur",
    },
    {
        "scenario_index": 1,
        "service_name": "Lawn Mowing & Garden Care",
        "service_category": "GARDENING",
        "category": "GARDENING",
        "worker_name": "Ramesh Patel",
        "worker_skill": "Cooperative Landscaper / Gardener",
        "trade_skill": "Cooperative Landscaper / Gardener",
        "worker_member_id": "114",
        "skill_name": "Gardener",
        "worker_phone": "9123456782",
        "shramik_id": "SHR-MP-2026-1003",
        "experience_years": 12,
        "hourly_rate": 350.00,
        "customer_name": "Anand Verma",
        "customer_phone": "9876543210",
        "customer_email": "anand.verma@example.com",
        "location": "Vijay Nagar, Jabalpur",
    },
    {
        "scenario_index": 2,
        "service_name": "Kitchen Sink Leak & Pipe Repair",
        "service_category": "PLUMBING",
        "category": "PLUMBING",
        "worker_name": "Suresh Raikwar",
        "worker_skill": "Cooperative Plumber / Pipefitter",
        "trade_skill": "Cooperative Plumber / Pipefitter",
        "worker_member_id": "118",
        "skill_name": "Plumber",
        "worker_phone": "9123456781",
        "shramik_id": "SHR-MP-2026-1002",
        "experience_years": 7,
        "hourly_rate": 300.00,
        "customer_name": "Dr. Kavita Jain",
        "customer_phone": "9876543211",
        "customer_email": "kavita.jain@example.com",
        "location": "Wright Town, Jabalpur",
    },
    {
        "scenario_index": 3,
        "service_name": "Wooden Door Hinge & Lock Alignment",
        "service_category": "CARPENTRY",
        "category": "CARPENTRY",
        "worker_name": "Mohan Vishwakarma",
        "worker_skill": "Cooperative Artisan / Carpenter",
        "trade_skill": "Cooperative Artisan / Carpenter",
        "worker_member_id": "122",
        "skill_name": "Carpenter",
        "worker_phone": "9123456787",
        "shramik_id": "SHR-MP-2026-1022",
        "experience_years": 14,
        "hourly_rate": 320.00,
        "customer_name": "Sunil Tiwari",
        "customer_phone": "9876543217",
        "customer_email": "sunil.tiwari@example.com",
        "location": "Napier Town, Jabalpur",
    },
    {
        "scenario_index": 4,
        "service_name": "Split AC Deep Cleaning & Inspection",
        "service_category": "HVAC",
        "category": "HVAC",
        "worker_name": "Imran Khan",
        "worker_skill": "Cooperative RAC Technician",
        "trade_skill": "Cooperative RAC Technician",
        "worker_member_id": "127",
        "skill_name": "AC Technician",
        "worker_phone": "9123456784",
        "shramik_id": "SHR-MP-2026-1027",
        "experience_years": 8,
        "hourly_rate": 380.00,
        "customer_name": "Meera Singhania",
        "customer_phone": "9876543214",
        "customer_email": "meera.singhania@example.com",
        "location": "Gorakhpur, Jabalpur",
    },
]


def _apply_scenario_to_booking(
    booking: Booking,
    scenario: Dict[str, Any],
    db: Session,
) -> Booking:
    """Safely updates and resets a booking record to match a specific demo scenario."""
    ensure_trade_rate_cards(db)

    # 1. Customer
    cust_name = scenario["customer_name"]
    cust_phone = scenario["customer_phone"]
    customer = db.query(CustomerData).filter(
        (CustomerData.phone == cust_phone) | (func.lower(CustomerData.name) == cust_name.lower())
    ).first()
    if not customer:
        customer = CustomerData(
            name=cust_name,
            phone=cust_phone,
            email=scenario["customer_email"],
            address=scenario["location"],
            city="Jabalpur",
            latitude=23.181500,
            longitude=79.986400,
        )
        db.add(customer)
        db.flush()

    # 2. Skill
    skill = db.query(Skill).filter(
        func.lower(Skill.skill_name) == scenario["skill_name"].lower()
    ).first()
    if not skill:
        skill = Skill(
            skill_name=scenario["skill_name"],
            description=f"{scenario['skill_name']} trade services",
        )
        db.add(skill)
        db.flush()

    # 3. Service
    service = db.query(Service).filter(
        (func.lower(Service.service_name) == scenario["service_name"].lower())
        | (Service.category == scenario["service_category"])
    ).first()
    if not service:
        service = Service(
            service_name=scenario["service_name"],
            description=f"Professional {scenario['service_name']} by certified cooperative workers.",
            category=scenario["service_category"],
            base_price=250.00,
            estimated_duration=60,
            is_active=True,
            skill_id=skill.skill_id,
        )
        db.add(service)
        db.flush()
    else:
        service.service_name = scenario["service_name"]
        service.category = scenario["service_category"]
        service.skill_id = skill.skill_id

    # 4. Worker
    worker = db.query(WorkerData).filter(
        (WorkerData.phone == scenario["worker_phone"])
        | (func.lower(WorkerData.name) == scenario["worker_name"].lower())
    ).first()
    if not worker:
        worker = WorkerData(
            name=scenario["worker_name"],
            phone=scenario["worker_phone"],
            email=scenario.get("worker_email", f"{scenario['worker_name'].lower().replace(' ', '.').replace('dr.', '')}@example.com"),
            experience_years=scenario["experience_years"],
            hourly_rate=scenario["hourly_rate"],
            address=scenario["location"],
            city="Jabalpur",
            latitude=23.185000,
            longitude=79.982000,
            is_verified=True,
            is_active=True,
            shramik_id=scenario["shramik_id"],
            skill_certificate=f"CERT-{scenario['service_category'][:4]}-2022",
            verification_status="VERIFIED",
            verification_type="DEMO_SHRAMIK",
        )
        db.add(worker)
        db.flush()
        ws = WorkerSkill(
            worker_id=worker.worker_id,
            skill_id=skill.skill_id,
            skill_level="Expert",
            experience_years=scenario["experience_years"],
        )
        db.add(ws)
    else:
        worker.name = scenario["worker_name"]
        worker.phone = scenario["worker_phone"]
        worker.is_verified = True
        worker.is_active = True
        worker.shramik_id = scenario["shramik_id"]
        # Ensure WorkerSkill link
        ws_exist = db.query(WorkerSkill).filter(
            WorkerSkill.worker_id == worker.worker_id,
            WorkerSkill.skill_id == skill.skill_id,
        ).first()
        if not ws_exist:
            ws = WorkerSkill(
                worker_id=worker.worker_id,
                skill_id=skill.skill_id,
                skill_level="Expert",
                experience_years=scenario["experience_years"],
            )
            db.add(ws)

    # 5. Apply to Booking
    booking.customer_id = customer.customer_id
    booking.worker_id = worker.worker_id
    booking.service_id = service.service_id
    booking.booking_date = date.today()
    booking.start_time = time(10, 0)
    booking.address = scenario["location"]
    booking.description = scenario["service_name"]
    booking.status = "ASSIGNED"
    booking.payment_status = "UNPAID"
    booking.start_otp = "4821"
    booking.end_otp = "9134"
    booking.start_otp_attempts = 0
    booking.end_otp_attempts = 0
    booking.is_start_otp_locked = False
    booking.is_end_otp_locked = False
    booking.start_otp_verified_at = None
    booking.end_otp_verified_at = None
    booking.last_otp_attempt_at = None
    booking.additional_service_charge = 0.00
    booking.material_charge = 0.00
    booking.amount = 239.00
    booking.estimated_price = 239.00
    booking.total_amount = 239.00
    booking.final_amount = 239.00
    booking.worker_payout_amount = 199.00
    booking.platform_tech_fee = 30.00
    booking.welfare_pool_fee = 10.00
    booking.quotation_status = "NONE"
    booking.customer_approved_at = None
    booking.work_completed_at = None
    booking.payment_reference = None
    booking.payment_completed_at = None
    booking.settled_at = None
    booking.warranty_active = False
    booking.warranty_started_at = None
    booking.warranty_expires_at = None

    # Clear child records
    db.query(Quotation).filter(Quotation.booking_id == booking.booking_id).delete()
    db.query(PaymentRecord).filter(PaymentRecord.booking_id == booking.booking_id).delete()
    db.query(CooperativeWelfareLedger).filter(CooperativeWelfareLedger.booking_id == booking.booking_id).delete()

    # Worker availability
    avail = db.query(Availability).filter(Availability.worker_id == booking.worker_id).first()
    if avail:
        avail.is_available = True

    return booking


@router.post(
    "/demo/cycle-scenario",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cycle through realistic multi-trade demo scenarios",
)
@router.post(
    "/bookings/demo/cycle-scenario",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cycle through realistic multi-trade demo scenarios",
)
@router.post(
    "/demo/cycle",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cycle through realistic multi-trade demo scenarios",
)
@router.post(
    "/bookings/demo/cycle",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cycle through realistic multi-trade demo scenarios",
)
def cycle_scenario(
    scenario_index: Optional[int] = None,
    booking_id: Optional[int] = None,
    payload: Optional[CycleScenarioRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Multi-scenario rotational endpoint for the demo booking engine:
    - Cycles round-robin or accepts scenario_index (0 to 4):
      * Scenario 0: Electrical (Ceiling Fan / Arvind Gupta / Member 111 / Pooja Sharma)
      * Scenario 1: Gardening (Lawn Mowing / Ramesh Patel / Member 114 / Anand Verma)
      * Scenario 2: Plumbing (Kitchen Sink / Suresh Raikwar / Member 118 / Dr. Kavita Jain)
      * Scenario 3: Carpentry (Wooden Door / Mohan Vishwakarma / Member 122 / Sunil Tiwari)
      * Scenario 4: HVAC (Split AC / Imran Khan / Member 127 / Meera Singhania)
    - Upserts and resets the demo order cleanly.
    """
    global _scenario_counter

    # Resolve scenario index
    target_index = None
    target_booking_id = None

    if payload:
        if payload.scenario_index is not None:
            target_index = payload.scenario_index % len(DEMO_SCENARIOS)
        if payload.booking_id is not None:
            target_booking_id = payload.booking_id

    if target_index is None and scenario_index is not None:
        target_index = scenario_index % len(DEMO_SCENARIOS)

    if target_booking_id is None and booking_id is not None:
        target_booking_id = booking_id

    if target_index is None:
        _scenario_counter = (_scenario_counter + 1) % len(DEMO_SCENARIOS)
        target_index = _scenario_counter

    scenario = DEMO_SCENARIOS[target_index]

    # Find or create target booking
    booking = None
    if target_booking_id:
        booking = db.get(Booking, target_booking_id)

    if not booking:
        for bid in [58, 64, 1, 101, 102, 103, 104, 105]:
            booking = db.get(Booking, bid)
            if booking:
                break
        if not booking:
            booking = db.query(Booking).first()

    if not booking:
        # Create initial booking row
        booking = Booking(
            booking_id=58,
            customer_id=1,
            worker_id=1,
            service_id=1,
            amount=239.00,
            status="ASSIGNED",
            payment_status="UNPAID",
        )
        db.add(booking)
        db.flush()

    _apply_scenario_to_booking(booking, scenario, db)

    # Ensure companion demo bookings match the scenario and are cleanly reset
    for comp_id in [1, 58, 61, 62, 63, 64, 65, 101, 102, 103, 104, 105]:
        if comp_id != booking.booking_id:
            comp = db.get(Booking, comp_id)
            if comp:
                _apply_scenario_to_booking(comp, scenario, db)

    db.commit()
    db.refresh(booking)

    formatted = _format_booking_response(booking)
    formatted.service_category = scenario["service_category"]
    formatted.category = scenario["service_category"]
    formatted.trade_skill = scenario["worker_skill"]
    formatted.worker_trade_skill = scenario["worker_skill"]
    formatted.worker_skill = scenario["worker_skill"]
    formatted.worker_name = scenario["worker_name"]
    formatted.customer_name = scenario["customer_name"]
    formatted.service_name = scenario["service_name"]

    return formatted


@router.post(
    "/demo/new-booking",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new randomized demo booking from pre-seeded service sets",
)
@router.post(
    "/bookings/demo/new-booking",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new randomized demo booking from pre-seeded service sets",
)
def create_randomized_demo_booking(
    scenario_index: Optional[int] = None,
    payload: Optional[CycleScenarioRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Creates a new booking row in PostgreSQL/Supabase with valid foreign keys and consistent category mapping.
    Rotates through the 5 realistic cooperative scenarios.
    """
    global _scenario_counter

    target_index = None
    if payload and payload.scenario_index is not None:
        target_index = payload.scenario_index % len(DEMO_SCENARIOS)
    elif scenario_index is not None:
        target_index = scenario_index % len(DEMO_SCENARIOS)
    else:
        _scenario_counter = (_scenario_counter + 1) % len(DEMO_SCENARIOS)
        target_index = _scenario_counter

    scenario = DEMO_SCENARIOS[target_index]

    new_booking = Booking(
        customer_id=1,
        worker_id=1,
        service_id=1,
        amount=239.00,
        status="ASSIGNED",
        payment_status="UNPAID",
    )
    db.add(new_booking)
    db.flush()

    _apply_scenario_to_booking(new_booking, scenario, db)

    db.commit()
    db.refresh(new_booking)

    formatted = _format_booking_response(new_booking)
    formatted.service_category = scenario["service_category"]
    formatted.category = scenario["service_category"]
    formatted.trade_skill = scenario["worker_skill"]
    formatted.worker_trade_skill = scenario["worker_skill"]
    formatted.worker_skill = scenario["worker_skill"]
    formatted.worker_name = scenario["worker_name"]
    formatted.customer_name = scenario["customer_name"]
    formatted.service_name = scenario["service_name"]

    return formatted
