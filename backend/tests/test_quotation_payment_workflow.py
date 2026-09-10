"""
tests/test_quotation_payment_workflow.py — Full Integration Tests for Inspection-First, Pay-After-Completion State Machine
Tests trade-specific rate cards, on-site quotations, customer approval/rejection, payment pending, settlement, Gullak & warranty.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Booking, RateCardItem, Quotation, CooperativeWelfareLedger, Skill

client = TestClient(app)


def test_1_normal_job_inspection_base_flow():
    """
    Scenario 1: Standard Job (₹239 base inspection charge)
    - Booking created (₹239 NOT collected at creation)
    - Start OTP 4821 verified -> in_progress
    - Work completed
    - Completion OTP 9134 verified -> payment_pending (no premature settlement or warranty)
    - Demo payment -> completed, PAID, ₹10 Gullak credited, 72h warranty activated
    """
    # 1. Create booking
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_scope": "Ceiling Fan Repair & Inspection",
        "location": "Civil Lines, Jabalpur",
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # 2. Verify Start OTP
    start_resp = client.post("/api/bookings/verify-start-otp", json={
        "booking_id": booking_id,
        "otp": "4821",
    })
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "in_progress"

    # 3. Mark work completed
    wc_resp = client.post(f"/api/bookings/{booking_id}/work-completed")
    assert wc_resp.status_code == 200
    assert wc_resp.json()["status"] == "WORK_COMPLETED"

    # 4. Completion OTP -> PAYMENT_PENDING
    end_resp = client.post("/api/bookings/verify-end-otp", json={
        "booking_id": booking_id,
        "otp": "9134",
    })
    assert end_resp.status_code == 200
    end_data = end_resp.json()
    assert end_data["status"] == "payment_pending"
    assert end_data["warranty_active"] is False  # Warranty not active before payment!

    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.status == "payment_pending"
        assert b.payment_status == "PENDING"
        assert b.warranty_active is False

    # 5. Execute Demo Pay -> COMPLETED
    pay_resp = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert pay_data["success"] is True
    assert pay_data["status"] == "completed"
    assert pay_data["payment_status"] == "paid"
    assert pay_data["amount_paid"] == 239.00
    assert pay_data["warranty_active"] is True
    assert pay_data["warranty_expires_at"] is not None
    assert pay_data["settlement_summary"]["worker_payout_amount"] == 199.00
    assert pay_data["settlement_summary"]["welfare_pool_fee"] == 10.00
    assert pay_data["settlement_summary"]["platform_tech_fee"] == 30.00

    # 6. Verify Database State
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        assert b.status == "COMPLETED"
        assert b.payment_status == "PAID"
        assert b.settled_at is not None
        assert b.warranty_active is True

        ledger = db.query(CooperativeWelfareLedger).filter(
            CooperativeWelfareLedger.booking_id == booking_id
        ).first()
        assert ledger is not None
        assert float(ledger.amount) == 10.00


def test_2_additional_work_approved_quotation_flow():
    """
    Scenario 2: Job with Approved Quotation (₹239 base + ₹250 additional = ₹489)
    - Booking created for Painting service (service_id=6, skill=Painter)
    - Start OTP 4821 verified -> in_progress
    - Fetch rate card -> verify only Painting items are returned
    - Worker submits Quotation for Primer (₹250)
    - Customer Approves Quotation -> final_amount updated to ₹489.00
    - Completion OTP 9134 verified -> payment_pending
    - Demo Payment -> settles ₹489.00 (₹449 worker + ₹30 tech + ₹10 Gullak)
    """
    # 1. Create painting booking (service_id=6)
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 6,
        "service_id": 6,
        "service_scope": "Interior Room Wall Painting",
        "location": "Wright Town, Jabalpur",
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # 2. Start OTP
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})

    # 3. Fetch trade-specific rate card
    rc_resp = client.get(f"/api/bookings/{booking_id}/rate-card")
    assert rc_resp.status_code == 200
    rc_items = rc_resp.json()["items"]
    assert len(rc_items) > 0

    # Verify no electrician items (like MCB or Capacitor) exist in painting rate card
    item_names = [it["item_name"].lower() for it in rc_items]
    assert not any("mcb" in name or "capacitor" in name for name in item_names)

    # Find Primer Coat Application (₹250.00)
    primer_item = next((it for it in rc_items if "primer" in it["item_name"].lower()), rc_items[0])
    unit_rate = primer_item["unit_rate"]

    # 4. Worker submits quotation
    quote_resp = client.post(f"/api/bookings/{booking_id}/quotation", json={
        "items": [{"rate_card_item_id": primer_item["item_id"], "quantity": 1}],
        "worker_notes": "Required primer sealer coat before emulsion application.",
    })
    assert quote_resp.status_code == 201
    quote_data = quote_resp.json()
    assert quote_data["status"] == "QUOTE_PENDING"
    assert quote_data["total_additional_amount"] == unit_rate

    # 5. Customer Approves Quotation
    approve_resp = client.post(f"/api/bookings/{booking_id}/quotation/approve", json={
        "customer_notes": "Approved for primer coat."
    })
    assert approve_resp.status_code == 200
    appr_data = approve_resp.json()
    expected_total = 239.00 + unit_rate
    assert appr_data["quotation_status"] == "QUOTE_APPROVED"
    assert appr_data["final_amount"] == expected_total

    # 6. Work completed
    client.post(f"/api/bookings/{booking_id}/work-completed")

    # 7. Completion OTP
    end_resp = client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    assert end_resp.status_code == 200
    assert end_resp.json()["status"] == "payment_pending"

    # 8. Demo Payment
    pay_resp = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert pay_data["amount_paid"] == expected_total
    assert pay_data["settlement_summary"]["total_settled"] == expected_total
    assert pay_data["settlement_summary"]["welfare_pool_fee"] == 10.00
    assert pay_data["settlement_summary"]["platform_tech_fee"] == 30.00
    assert pay_data["settlement_summary"]["worker_payout_amount"] == expected_total - 40.00


def test_3_quotation_rejection_reverts_to_base_amount():
    """
    Scenario 3: Customer Rejects Quotation
    - Quotation is rejected -> final_amount remains base ₹239.00
    - Payment collects only ₹239.00
    """
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})

    rc_resp = client.get(f"/api/bookings/{booking_id}/rate-card")
    rc_item = rc_resp.json()["items"][0]

    # Submit quote
    client.post(f"/api/bookings/{booking_id}/quotation", json={
        "items": [{"rate_card_item_id": rc_item["item_id"], "quantity": 1}],
    })

    # Reject quote
    rej_resp = client.post(f"/api/bookings/{booking_id}/quotation/reject", json={
        "customer_notes": "Not needed right now."
    })
    assert rej_resp.status_code == 200
    data = rej_resp.json()
    assert data["quotation_status"] == "QUOTE_REJECTED"
    assert data["final_amount"] == 239.00

    # Settle
    client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})
    pay_resp = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay_resp.status_code == 200
    assert pay_resp.json()["amount_paid"] == 239.00


def test_4_cross_trade_rate_card_item_rejected():
    """
    Scenario 4: Security / Trade Skill Isolation Check
    - A Painting booking attempts to submit an Electrical rate card item.
    - System MUST reject with 400 Bad Request to prevent skill-card mismatch.
    """
    # Painting booking (service_id=6)
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 6,
        "service_id": 6,
    })
    booking_id = create_resp.json()["booking_id"]
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})

    # Fetch Electrician rate card item (skill_id=1)
    with SessionLocal() as db:
        elec_item = db.query(RateCardItem).filter(RateCardItem.skill_id == 1).first()
        assert elec_item is not None
        elec_item_id = elec_item.item_id

    # Try to add Electrician item to Painting booking
    mismatch_resp = client.post(f"/api/bookings/{booking_id}/quotation", json={
        "items": [{"rate_card_item_id": elec_item_id, "quantity": 1}],
    })
    assert mismatch_resp.status_code == 400
    assert "does not match booking trade skill" in mismatch_resp.json()["detail"]


def test_5_payment_idempotency_prevents_duplicate_settlement():
    """
    Scenario 5: Settlement Idempotency
    - Paying twice returns 200 without creating duplicate Gullak entries.
    """
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    booking_id = create_resp.json()["booking_id"]
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})
    client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})

    pay1 = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay1.status_code == 200

    # Second payment call
    pay2 = client.post(f"/api/bookings/{booking_id}/demo-pay")
    assert pay2.status_code == 200
    assert "already" in pay2.json()["message"].lower()

    # Check exactly 1 Gullak entry
    with SessionLocal() as db:
        gullak_count = db.query(CooperativeWelfareLedger).filter(
            CooperativeWelfareLedger.booking_id == booking_id
        ).count()
        assert gullak_count == 1


def test_6_demo_reset_endpoint():
    """
    Scenario 6: Demo Reset Endpoint
    - Safely resets demo booking 1 without dropping database tables or production records.
    """
    reset_resp = client.post("/api/demo/reset?booking_id=1")
    assert reset_resp.status_code == 200
    data = reset_resp.json()
    assert data["success"] is True
    assert data["booking_id"] == 1
    assert data["status"] == "pending"
    assert data["start_otp"] == "4821"
    assert data["end_otp"] == "9134"

    with SessionLocal() as db:
        b = db.get(Booking, 1)
        if b:
            assert b.status == "pending"
            assert b.payment_status == "PENDING"
            assert b.is_start_otp_locked is False
            assert b.is_end_otp_locked is False
            assert b.warranty_active is False
            assert b.quotation_status == "NONE"
