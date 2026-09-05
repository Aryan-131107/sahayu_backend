"""
tests/test_dual_otp_welfare.py — Tests for Dual-OTP State Machine & Cooperative Welfare Ledger (Slide 3)
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Booking, CooperativeWelfareLedger

client = TestClient(app)


def test_create_dual_otp_booking():
    """POST /api/bookings/create initializes booking with Start PIN 4821, End PIN 9134, and Slide 3 pricing."""
    payload = {
        "customer_id": 1,
        "worker_id": 1,
        "service_scope": "Electrical Inspection & Fault Diagnosis",
        "location": "Civil Lines, Jabalpur",
    }
    resp = client.post("/api/bookings/create", json=payload)
    assert resp.status_code == 201, f"Failed to create booking: {resp.text}"
    data = resp.json()

    assert data["status"] == "pending"
    assert data["start_otp"] == "4821"
    assert data["end_otp"] == "9134"
    assert data["service_scope"] == "Electrical Inspection & Fault Diagnosis"
    assert data["location"] == "Civil Lines, Jabalpur"
    assert "booking_reference" in data
    assert data["booking_reference"].startswith("SH-")

    pricing = data["pricing"]
    assert pricing["worker_payout"] == 199.00
    assert pricing["platform_tech_fee"] == 30.00
    assert pricing["welfare_pool_fee"] == 10.00
    assert pricing["total_amount"] == 239.00
    assert pricing["currency"] == "INR"


def test_verify_start_otp_success_and_failure():
    """POST /api/bookings/verify-start-otp validates PIN 4821 and updates status to in_progress."""
    # 1. Create fresh booking
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_scope": "Electrical Inspection & Fault Diagnosis",
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # 2. Test invalid start OTP
    fail_resp = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "0000",
    })
    assert fail_resp.status_code == 400
    assert "Invalid Start OTP" in fail_resp.json()["detail"]

    # 3. Test valid start OTP
    success_resp = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "4821",
    })
    assert success_resp.status_code == 200
    data = success_resp.json()
    assert data["status"] == "in_progress"
    assert data["arrival_confirmed"] is True
    assert data["booking_reference"].startswith("SH-")


def test_verify_end_otp_settlement_and_welfare_credit():
    """POST /api/bookings/verify-end-otp validates PIN 9134, settles payment, activates 72h warranty, and credits Welfare DB."""
    # 1. Create and start booking
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    start_resp = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "4821",
    })
    assert start_resp.status_code == 200

    # 2. Test invalid end OTP
    fail_resp = client.post("/api/bookings/verify-end-otp", json={
        "booking_id": booking_id,
        "otp": "1234",
    })
    assert fail_resp.status_code == 400
    assert "Invalid End OTP" in fail_resp.json()["detail"]

    # 3. Test valid end OTP
    success_resp = client.post("/api/bookings/verify-end-otp", json={
        "booking_id": booking_id,
        "otp": "9134",
    })
    assert success_resp.status_code == 200
    data = success_resp.json()
    assert data["status"] == "completed"
    assert data["warranty_active"] is True
    assert data["warranty_expires_at"] is not None

    settlement = data["settlement_summary"]
    assert settlement["worker_payout_released"] == 199.00
    assert settlement["welfare_gullak_credited"] == 10.00
    assert settlement["platform_tech_fee_retained"] == 30.00
    assert settlement["total_settled"] == 239.00

    # 4. Verify that a row was inserted into cooperative_welfare_ledger
    with SessionLocal() as db:
        ledger_entry = db.query(CooperativeWelfareLedger).filter(
            CooperativeWelfareLedger.booking_id == booking_id
        ).first()
        assert ledger_entry is not None
        assert float(ledger_entry.amount) == 10.00
        assert ledger_entry.entry_type == "CREDIT"
        assert ledger_entry.society_id == 1


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
    # Test on /bookings/create
    resp1 = client.post("/bookings/create", json={"customer_id": 1, "worker_id": 1})
    assert resp1.status_code == 201
    b_id = resp1.json()["booking_id"]

    # Test on /bookings/verify-start-otp
    resp2 = client.post("/bookings/verify-start-otp", json={"booking_id": b_id, "otp": "4821"})
    assert resp2.status_code == 200

    # Test on /bookings/verify-end-otp
    resp3 = client.post("/bookings/verify-end-otp", json={"booking_id": b_id, "otp": "9134"})
    assert resp3.status_code == 200

    # Test on /bookings/welfare-fund/summary
    resp4 = client.get("/bookings/welfare-fund/summary")
    assert resp4.status_code == 200
