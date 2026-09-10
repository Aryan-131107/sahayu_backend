"""
tests/test_dual_otp_welfare.py — Tests for Dual-OTP State Machine, Attempt Tracking & Cooperative Welfare Ledger (Slide 3)
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Booking, CooperativeWelfareLedger

client = TestClient(app)


# ─────────────────────────────────────────────────────────
# TEST 1: Correct START OTP → IN_PROGRESS
# ─────────────────────────────────────────────────────────
def test_1_correct_start_otp_transitions_to_in_progress():
    """Correct START OTP (4821) transitions booking status from pending to in_progress."""
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_scope": "Electrical Inspection & Fault Diagnosis",
        "location": "Civil Lines, Jabalpur",
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    verify_resp = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "4821",
    })
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["success"] is True
    assert data["status"] == "in_progress"
    assert data["arrival_confirmed"] is True
    assert data["verification_timestamp"] is not None

    # Verify DB state
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.status == "in_progress"
        assert b.start_otp_verified_at is not None


# ─────────────────────────────────────────────────────────
# TEST 2: Wrong START OTP → attempt count increases → booking unchanged
# ─────────────────────────────────────────────────────────
def test_2_wrong_start_otp_increments_attempts_and_keeps_state():
    """Wrong START OTP increments attempt counter and leaves booking in pending state."""
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # Wrong attempt 1
    fail1 = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "0000",
    })
    assert fail1.status_code == 400
    assert "Attempt 1 of 3" in fail1.json()["detail"]

    # Check DB
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.status == "pending"
        assert b.start_otp_attempts == 1
        assert b.is_start_otp_locked is False

    # Wrong attempt 2
    fail2 = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "1111",
    })
    assert fail2.status_code == 400
    assert "Attempt 2 of 3" in fail2.json()["detail"]

    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.status == "pending"
        assert b.start_otp_attempts == 2


# ─────────────────────────────────────────────────────────
# TEST 3: Wrong OTP 3 times → verification locked
# ─────────────────────────────────────────────────────────
def test_3_wrong_otp_3_times_locks_verification():
    """Submitting wrong OTP 3 times locks verification and rejects subsequent attempts."""
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # 3 wrong attempts
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "0001"})
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "0002"})
    fail3 = client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "0003"})
    assert fail3.status_code == 400
    assert "Maximum verification attempts reached" in fail3.json()["detail"]

    # Verify locked in DB
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.is_start_otp_locked is True
        assert b.start_otp_attempts == 3

    # Even if the correct PIN is provided now, it must be locked!
    locked_resp = client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})
    assert locked_resp.status_code == 400
    assert "locked" in locked_resp.json()["detail"].lower()


# ─────────────────────────────────────────────────────────
# TEST 4: Correct END OTP → PAYMENT_PENDING → Demo Pay → Settlement, ₹10 Gullak credit, warranty activated
# ─────────────────────────────────────────────────────────
def test_4_correct_end_otp_settles_and_activates_warranty_and_credits_gullak():
    """Correct END OTP (9134) transitions to payment_pending; Demo Pay settles payment, credits ₹10 to Gullak, and activates 72h warranty."""
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]

    # Start booking
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})

    # Complete with END OTP -> payment_pending
    end_resp = client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    assert end_resp.status_code == 200
    data = end_resp.json()
    assert data["success"] is True
    assert data["status"] == "payment_pending"

    # Pay to finalize settlement and activate warranty
    pay_resp = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()

    assert pay_data["success"] is True
    assert pay_data["status"] == "completed"
    assert pay_data["warranty_active"] is True
    assert pay_data["warranty_expires_at"] is not None
    assert pay_data["settlement_summary"]["worker_payout_amount"] == 199.00
    assert pay_data["settlement_summary"]["welfare_pool_fee"] == 10.00
    assert pay_data["settlement_summary"]["platform_tech_fee"] == 30.00
    assert pay_data["settlement_summary"]["total_settled"] == 239.00

    # Verify Gullak Ledger entry created in DB
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.status == "COMPLETED"
        assert b.payment_status == "PAID"
        assert b.warranty_active is True

        ledger = db.query(CooperativeWelfareLedger).filter(
            CooperativeWelfareLedger.booking_id == booking_id
        ).first()
        assert ledger is not None
        assert float(ledger.amount) == 10.00
        assert ledger.entry_type == "CREDIT"
        assert ledger.society_id == 1


# ─────────────────────────────────────────────────────────
# TEST 5: Wrong END OTP → booking unchanged → no settlement → no Gullak entry → no warranty
# ─────────────────────────────────────────────────────────
def test_5_wrong_end_otp_no_settlement_no_gullak_no_warranty():
    """Wrong END OTP leaves booking in_progress, with no settlement, no Gullak credit, and no warranty."""
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})

    # Wrong End OTP
    fail_resp = client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "0000"})
    assert fail_resp.status_code == 400
    assert "Invalid Completion PIN" in fail_resp.json()["detail"]

    # Verify DB unchanged
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.status == "in_progress"
        assert b.payment_status == "PENDING"
        assert b.warranty_active is False
        assert b.end_otp_attempts == 1

        ledger = db.query(CooperativeWelfareLedger).filter(
            CooperativeWelfareLedger.booking_id == booking_id
        ).first()
        assert ledger is None


# ─────────────────────────────────────────────────────────
# TEST 6: Repeat END OTP → rejected → no duplicate settlement
# ─────────────────────────────────────────────────────────
def test_6_repeat_end_otp_rejected_no_duplicate_settlement():
    """Repeating END OTP on an already completed booking is rejected with 409 Conflict without duplicate Gullak entries."""
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})
    resp1 = client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    assert resp1.status_code == 200

    # Settle payment
    client.post(f"/api/bookings/{booking_id}/demo-pay")

    # Repeat END OTP request on completed booking
    repeat_resp = client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    assert repeat_resp.status_code == 409

    # Verify exactly ONE ledger row in DB
    with SessionLocal() as db:
        entries = db.query(CooperativeWelfareLedger).filter(
            CooperativeWelfareLedger.booking_id == booking_id
        ).all()
        assert len(entries) == 1


# ─────────────────────────────────────────────────────────
# TEST 7: Refresh/re-fetch booking → correct state returned
# ─────────────────────────────────────────────────────────
def test_7_refresh_refetch_booking_persists_state():
    """Re-fetching booking from database returns exact current state including OTP attempts and warranty."""
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})
    client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    client.post(f"/api/bookings/{booking_id}/demo-pay")

    # Fetch booking by ID
    get_resp = client.get(f"/api/bookings/{booking_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["booking_id"] == booking_id
    assert data["status"].lower() == "completed"
    assert data["warranty_active"] is True
    assert data["warranty_expires_at"] is not None
    assert data["worker_payout_amount"] == 199.00
    assert data["welfare_pool_fee"] == 10.00
    assert data["platform_tech_fee"] == 30.00
    assert data["total_amount"] == 239.00


# ─────────────────────────────────────────────────────────
# TEST 8: State Machine Guard (Cannot skip Start OTP or End OTP)
# ─────────────────────────────────────────────────────────
def test_8_wrong_state_transitions_rejected():
    """Cannot verify End OTP before Start OTP verification."""
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]

    # Try to verify End OTP directly on pending booking
    early_end = client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    assert early_end.status_code == 409
    assert "Start OTP must be verified first" in early_end.json()["detail"] or "state" in early_end.json()["detail"].lower()


# ─────────────────────────────────────────────────────────
# TEST 9: Warranty expiry timestamp → exactly 72 hours from payment
# ─────────────────────────────────────────────────────────
def test_9_warranty_expiry_timestamp_exactly_72_hours():
    """Warranty expiry timestamp is set to exactly 72 hours (3 days) from payment completion time."""
    before_time = datetime.now()
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})
    client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    pay_resp = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay_resp.status_code == 200
    after_time = datetime.now()

    data = pay_resp.json()
    expires_at_str = data["warranty_expires_at"]
    # Handle ISO formats
    if expires_at_str.endswith("Z"):
        expires_at_str = expires_at_str[:-1] + "+00:00"
    expires_at = datetime.fromisoformat(expires_at_str).replace(tzinfo=None)

    expected_min = before_time + timedelta(days=3) - timedelta(seconds=5)
    expected_max = after_time + timedelta(days=3) + timedelta(seconds=5)

    assert expected_min <= expires_at <= expected_max


# ─────────────────────────────────────────────────────────
# WELFARE DB SUMMARY & ROUTE MOUNTS
# ─────────────────────────────────────────────────────────
def test_welfare_fund_summary_endpoint():
    """GET /api/bookings/welfare-fund/summary aggregates Gullak reserve fund metrics."""
    resp = client.get("/api/bookings/welfare-fund/summary?society_id=1")
    assert resp.status_code == 200
    data = resp.json()

    assert data["society_id"] == 1
    assert "total_gullak_reserve" in data
    assert data["total_gullak_reserve"] > 0
    assert "total_contributions_count" in data
    assert data["total_contributions_count"] >= 1
    assert data["governing_body"] == "Jabalpur District Cooperative Federation"
    assert data["currency"] == "INR"


def test_direct_root_route_mounts():
    """Ensure Dual-OTP endpoints work under both /api/bookings and /bookings."""
    resp1 = client.post("/bookings/create", json={"customer_id": 1, "worker_id": 1})
    assert resp1.status_code == 201
    b_id = resp1.json()["booking_id"]

    resp2 = client.post("/bookings/verify-start-otp", json={"booking_id": b_id, "otp": "4821"})
    assert resp2.status_code == 200

    resp3 = client.post("/bookings/verify-end-otp", json={"booking_id": b_id, "otp": "9134"})
    assert resp3.status_code == 200

    resp4 = client.get("/bookings/welfare-fund/summary")
    assert resp4.status_code == 200
