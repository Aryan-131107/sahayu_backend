"""
tests/test_confirm_booking_flow.py — Verification of 'Confirm Service Booking (Pay ₹239 After Job)' Flow
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_confirm_service_booking_ac_servicing_santosh_mishra():
    """
    Exact scenario:
    - Service: AC Servicing & Gas Refill (Service ID: 11)
    - Worker: Santosh Mishra (Worker ID: 9)
    - Location: Civil Lines, Jabalpur
    - Date: 2026-09-10
    - Time: 'Morning'
    - Upfront Payment: ₹0 (Payment status = PENDING)
    - Base total payable after job: ₹239.00
    - Start OTP: 4821, Completion OTP: 9134
    """
    payload = {
        "customer_id": 1,
        "worker_id": 9,
        "service_id": 11,
        "booking_date": "2026-09-10",
        "start_time": "Morning",
        "address": "Civil Lines, Jabalpur",
        "description": "AC Servicing & Gas Refill",
        "amount": 239.00,
    }

    # 1. Click Confirm Service Booking
    resp = client.post("/api/bookings", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    booking_id = data["booking_id"]
    assert data["booking_reference"].startswith("SH-")
    assert data["worker_name"] == "Santosh Mishra"
    assert data["service_name"] == "AC Servicing & Gas Refill"
    assert data["status"] in ["PENDING", "CONFIRMED"]
    assert data["payment_status"] == "PENDING"
    assert data["total_amount"] == 239.00
    assert data["final_amount"] == 239.00
    assert data["worker_payout_amount"] == 199.00
    assert data["platform_tech_fee"] == 30.00
    assert data["welfare_pool_fee"] == 10.00
    assert data["start_otp"] == "4821"
    assert data["end_otp"] == "9134"
    assert data["completion_otp"] == "9134"
    assert data["warranty_active"] is False
    assert data["settled_at"] is None
    assert data["payment_reference"] is None

    # 2. Idempotency test (double click confirm)
    repeat_resp = client.post("/api/bookings", json=payload)
    assert repeat_resp.status_code == 201
    repeat_data = repeat_resp.json()
    assert repeat_data["booking_id"] == booking_id

    # 3. Step: Doorstep Arrival -> Start OTP 4821
    start_resp = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "4821",
    })
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "in_progress"

    # 4. Step: Worker adds approved quotation (+₹350 labor, +₹450 material)
    rate_card_resp = client.get(f"/api/bookings/{booking_id}/rate-card")
    assert rate_card_resp.status_code == 200
    items = rate_card_resp.json()["items"]
    assert len(items) > 0

    quote_resp = client.post(f"/api/bookings/{booking_id}/quotation", json={
        "additional_labor_charge": 350.00,
        "additional_material_charge": 450.00,
        "worker_notes": "AC Compressor cleaning and capacitor replacement",
        "items": [
            {
                "rate_card_item_id": items[0]["item_id"],
                "quantity": 1,
            }
        ]
    })
    assert quote_resp.status_code == 201

    # Customer approves quotation
    total_added = quote_resp.json()["total_additional_amount"]
    approve_resp = client.post(f"/api/bookings/{booking_id}/quotation/approve", json={
        "customer_notes": "Approved for compressor fix."
    })
    assert approve_resp.status_code == 200
    assert approve_resp.json()["final_amount"] == 239.00 + total_added

    # 5. Step: Work Completed
    work_resp = client.post(f"/api/bookings/{booking_id}/work-completed")
    assert work_resp.status_code == 200
    assert work_resp.json()["status"] == "WORK_COMPLETED"

    # 6. Step: Completion OTP 9134 -> Transitions to payment_pending
    end_resp = client.post("/api/bookings/verify-end-otp", json={
        "booking_id": booking_id,
        "otp": "9134",
    })
    assert end_resp.status_code == 200
    assert end_resp.json()["status"] == "payment_pending"

    # 7. Step: Customer completes payment -> COMPLETED, PAID, Gullak credited, 72h warranty active
    pay_resp = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert pay_data["status"] == "completed"
    assert pay_data["payment_status"] == "paid"
    assert pay_data["amount_paid"] == 239.00 + total_added
    assert pay_data["warranty_active"] is True
    assert pay_data["settlement_summary"]["welfare_gullak_credited"] == 10.00


def test_rate_card_and_welfare_endpoints_not_shadowed_by_booking_id():
    """Verify that static endpoints (/rate-card, /welfare-fund/summary) are not intercepted by /{booking_id}."""
    # 1. Test GET /api/bookings/rate-card
    rc_resp = client.get("/api/bookings/rate-card?skill_id=9")
    assert rc_resp.status_code == 200
    assert rc_resp.json()["skill_id"] == 9
    assert len(rc_resp.json()["items"]) > 0

    # 2. Test GET /bookings/rate-card (direct root)
    rc_root_resp = client.get("/bookings/rate-card?skill_id=9")
    assert rc_root_resp.status_code == 200
    assert rc_root_resp.json()["skill_id"] == 9

    # 3. Test GET /api/bookings/welfare-fund/summary
    wf_resp = client.get("/api/bookings/welfare-fund/summary")
    assert wf_resp.status_code == 200
    assert "total_gullak_reserve" in wf_resp.json()

    # 4. Test GET /api/bookings/1 (parameterized)
    b_resp = client.get("/api/bookings/1")
    assert b_resp.status_code == 200
    assert b_resp.json()["booking_id"] == 1
