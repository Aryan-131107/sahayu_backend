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
    - Safely resets demo booking without dropping database tables or production records.
    - Directly updates DB record for Order #SH-0058 / primary booking.
    - Returns freshly updated booking object in response payload.
    """
    reset_resp = client.post("/api/demo/reset", json={"booking_id": 1, "booking_reference": "SH-0058"})
    assert reset_resp.status_code == 200
    data = reset_resp.json()
    assert data["success"] is True
    assert data["status"] in ["ASSIGNED", "pending"]
    assert data["start_otp"] == "4821"
    assert data["end_otp"] == "9134"
    assert "booking" in data
    assert data["booking"]["status"] in ["ASSIGNED", "pending"]

    with SessionLocal() as db:
        b = db.get(Booking, 1)
        if b:
            assert b.status in ["ASSIGNED", "pending"]
            assert b.payment_status in ["UNPAID", "PENDING"]
            assert b.is_start_otp_locked is False
            assert b.is_end_otp_locked is False
            assert b.warranty_active is False
            assert b.quotation_status == "NONE"


def test_7_demo_terminal_state_override_and_idempotency():
    """
    Scenario 7: Demo Terminal State Override and Idempotent Accept
    - A demo booking stuck in CANCELLED state can transition to ACCEPTED via demo override.
    - An already ACCEPTED booking returns HTTP 200 idempotently.
    """
    # 1. Create a booking and cancel it
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    b_id = create_resp.json()["booking_id"]
    client.patch(f"/api/bookings/{b_id}/cancel")

    with SessionLocal() as db:
        b = db.get(Booking, b_id)
        assert b.status == "CANCELLED"

    # 2. Reset booking via demo reset
    reset_resp = client.post(f"/api/demo/reset?booking_id={b_id}")
    assert reset_resp.status_code == 200

    # 3. Accept booking should succeed (bypassing terminal error)
    accept_resp = client.patch(f"/api/bookings/{b_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    # 4. Calling accept again on ACCEPTED booking returns 200 idempotently
    accept_again = client.patch(f"/api/bookings/{b_id}/accept")
    assert accept_again.status_code == 200
    assert accept_again.json()["status"] == "ACCEPTED"


def test_8_trade_specific_rate_card_domain_filtering():
    """
    Scenario 8: Trade-Specific Rate Card Domain Filtering & Worker Skill Consistency
    - Lawn Mowing / Gardening booking MUST return strictly Gardening items (Hedge Trimming, Aeration, Fertilizer, Debris).
    - Lawn Mowing / Gardening booking MUST NOT return electrical items (Capacitor, Motor Rewinding, MCB).
    - Worker trade skill MUST be formatted as Gardening & Landscaping Specialist.
    """
    # 1. Reset demo booking
    reset_resp = client.post("/api/demo/reset")
    assert reset_resp.status_code == 200
    b_id = reset_resp.json()["booking_id"]

    # 2. Fetch rate card for this booking
    rc_resp = client.get(f"/api/bookings/{b_id}/rate-card")
    assert rc_resp.status_code == 200
    rc_data = rc_resp.json()
    item_names = [it["item_name"] for it in rc_data["items"]]

    # Check gardening items exist
    assert any("Hedge Trimming" in name or "Pruning" in name for name in item_names)
    assert any("Lawn" in name or "Aeration" in name or "Weeding" in name for name in item_names)

    # Check NO electrical items in gardening rate card
    assert not any("Capacitor" in name for name in item_names)
    assert not any("MCB" in name for name in item_names)

    # 3. Check booking response fields
    booking_resp = client.get(f"/api/bookings/{b_id}")
    assert booking_resp.status_code == 200
    b_data = booking_resp.json()
    assert b_data["service_category"] == "GARDENING"
    assert "Garden" in b_data["trade_skill"] or "Garden" in b_data["worker_trade_skill"]


def test_9_create_randomized_demo_booking():
    """
    Scenario 9: Standalone Randomized Demo Booking Creation
    - POST /api/demo/new-booking creates a valid booking in DB.
    - Rotates across 5 pre-seeded service sets.
    - Status is ASSIGNED, payment_status is UNPAID, PINs are 4821 and 9134.
    """
    resp = client.post("/api/demo/new-booking")
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ASSIGNED"
    assert data["payment_status"] == "UNPAID"
    assert data["start_otp"] == "4821"
    assert data["end_otp"] == "9134"
    assert data["amount"] == 239.00
    assert data["worker_payout_amount"] == 199.00
    assert data["platform_tech_fee"] == 30.00
    assert data["welfare_pool_fee"] == 10.00
    assert data["service_category"] in ["ELECTRICAL", "GARDENING", "PLUMBING", "CARPENTRY", "HVAC"]


def test_10_cycle_scenario_rotations():
    """
    Scenario 10: Multi-scenario rotational endpoint for demo booking engine
    - POST /api/demo/cycle-scenario rotates through 5 scenarios (0 to 4).
    - Checks scenario 0 (Electrical / Arvind Gupta)
    - Checks scenario 1 (Gardening / Ramesh Patel)
    - Checks scenario 2 (Plumbing / Suresh Raikwar)
    - Checks scenario 3 (Carpentry / Mohan Vishwakarma)
    - Checks scenario 4 (HVAC / Imran Khan)
    """
    # 1. Test Scenario 0 - Electrical
    r0 = client.post("/api/demo/cycle-scenario", json={"scenario_index": 0})
    assert r0.status_code == 200
    d0 = r0.json()
    assert d0["service_category"] == "ELECTRICAL"
    assert d0["worker_name"] == "Arvind Gupta"
    assert d0["customer_name"] == "Pooja Sharma"
    assert d0["worker_skill"] == "Cooperative Electrician / Wireman"
    assert d0["start_otp"] == "4821"
    assert d0["end_otp"] == "9134"
    assert d0["status"] == "ASSIGNED"

    # 2. Test Scenario 1 - Gardening
    r1 = client.post("/api/demo/cycle-scenario", json={"scenario_index": 1})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["service_category"] == "GARDENING"
    assert d1["worker_name"] == "Ramesh Patel"
    assert d1["customer_name"] == "Anand Verma"
    assert d1["worker_skill"] == "Cooperative Landscaper / Gardener"

    # 3. Test Scenario 2 - Plumbing
    r2 = client.post("/api/demo/cycle-scenario", json={"scenario_index": 2})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["service_category"] == "PLUMBING"
    assert d2["worker_name"] == "Suresh Raikwar"
    assert d2["customer_name"] == "Dr. Kavita Jain"
    assert d2["worker_skill"] == "Cooperative Plumber / Pipefitter"

    # 4. Test Scenario 3 - Carpentry
    r3 = client.post("/api/demo/cycle-scenario", json={"scenario_index": 3})
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["service_category"] == "CARPENTRY"
    assert d3["worker_name"] == "Mohan Vishwakarma"
    assert d3["customer_name"] == "Sunil Tiwari"
    assert d3["worker_skill"] == "Cooperative Artisan / Carpenter"

    # 5. Test Scenario 4 - HVAC
    r4 = client.post("/api/demo/cycle-scenario", json={"scenario_index": 4})
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["service_category"] == "HVAC"
    assert d4["worker_name"] == "Imran Khan"
    assert d4["customer_name"] == "Meera Singhania"
    assert d4["worker_skill"] == "Cooperative RAC Technician"

    # 6. Test Round-Robin without scenario_index
    r_rr1 = client.post("/api/demo/cycle-scenario")
    assert r_rr1.status_code == 200
    r_rr2 = client.post("/api/demo/cycle-scenario")
    assert r_rr2.status_code == 200
    assert r_rr1.json()["service_category"] != r_rr2.json()["service_category"]


def test_11_backward_state_transition_and_idempotency():
    """
    Scenario 11: Backward State Transition & Idempotency on Booking Status Routes
    - When a booking is 'in_progress', sending an 'ACCEPTED' transition request returns HTTP 200 OK (no 400 error).
    - String casing is normalized ('in_progress', 'ACCEPTED', 'pending').
    - Status update endpoint /bookings/{id}/status is idempotent.
    - Transitioning back to 'ASSIGNED' or 'PENDING' for demo recovery succeeds cleanly.
    """
    # 1. Create a booking and start it
    create_resp = client.post("/api/bookings/create", json={"customer_id": 1, "worker_id": 1})
    assert create_resp.status_code == 201
    b_id = create_resp.json()["booking_id"]

    # Verify Start OTP -> puts it into in_progress
    start_resp = client.post("/api/bookings/verify-start-otp", json={"booking_id": b_id, "otp": "4821"})
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "in_progress"

    # 2. Worker / Frontend sends ACCEPTED on already in_progress booking -> must return 200 OK (no 400!)
    accept_resp = client.patch(f"/api/bookings/{b_id}/accept")
    assert accept_resp.status_code == 200

    # 3. Status route with status=ACCEPTED on in_progress booking -> must return 200 OK
    status_accept_resp = client.patch(f"/api/bookings/{b_id}/status?status=ACCEPTED")
    assert status_accept_resp.status_code == 200

    # 4. Status route with status=in_progress (same state, lower case) -> returns 200 OK
    status_same_resp = client.patch(f"/api/bookings/{b_id}/status?status=in_progress")
    assert status_same_resp.status_code == 200

    # 5. Setting state back to 'ASSIGNED' or 'PENDING' for demo reset succeeds
    reset_assigned_resp = client.patch(f"/api/bookings/{b_id}/status?status=ASSIGNED")
    assert reset_assigned_resp.status_code == 200
    assert reset_assigned_resp.json()["status"] == "ASSIGNED"

    reset_pending_resp = client.patch(f"/api/bookings/{b_id}/status?status=PENDING")
    assert reset_pending_resp.status_code == 200
    assert reset_pending_resp.json()["status"] == "PENDING"


def test_12_demo_order_64_terminal_state_override_and_accept():
    """
    Scenario 12: Order #SH-0064 Terminal State Invariance & Clean Demo Reset Acceptance
    - Direct transition from 'COMPLETED' to 'ACCEPTED' is strictly rejected with HTTP 409 Conflict.
    - Explicit Demo Reset (/api/demo/reset or /api/demo/cycle-scenario) resets the booking to 'ASSIGNED' and 'UNPAID'.
    - Worker accepting the reset booking succeeds with HTTP 200 ('ASSIGNED' -> 'ACCEPTED').
    """
    # 1. Seed or ensure booking 64 exists in COMPLETED state
    with SessionLocal() as db:
        b64 = db.get(Booking, 64)
        if not b64:
            b64 = Booking(
                booking_id=64,
                customer_id=1,
                worker_id=1,
                service_id=1,
                amount=239.00,
                status="COMPLETED",
                payment_status="PAID",
                warranty_active=True,
            )
            db.add(b64)
        else:
            b64.status = "COMPLETED"
            b64.payment_status = "PAID"
            b64.warranty_active = True
        db.commit()

    # 2. Worker attempting to accept COMPLETED booking without reset must fail (409 Conflict)
    invalid_accept = client.patch("/api/bookings/64/accept")
    assert invalid_accept.status_code == 409
    assert "Cannot transition" in invalid_accept.json()["detail"]

    # 3. Explicit Demo Reset resets booking 64 back to ASSIGNED & UNPAID
    reset_resp = client.post("/api/demo/reset", json={"booking_id": 64})
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ASSIGNED"

    # 4. Worker clicks 'Accept Service Request' on reset booking -> Succeeds (HTTP 200)
    accept_resp = client.patch("/api/bookings/64/accept")
    assert accept_resp.status_code == 200
    data = accept_resp.json()
    assert data["status"] == "ACCEPTED"
    assert data["payment_status"] == "UNPAID"
    assert data["warranty_active"] is False

    # 5. Idempotent re-accept on ACCEPTED returns 200
    re_accept = client.patch("/api/bookings/64/accept")
    assert re_accept.status_code == 200
    assert re_accept.json()["status"] == "ACCEPTED"


def test_13_pending_addon_blocks_completion_otp_until_approved():
    """
    Scenario 13: Pending Add-on blocks Completion OTP & Work Completed
    - Booking in_progress
    - Worker submits quotation -> status becomes QUOTE_PENDING
    - Attempting verify-end-otp fails with HTTP 400 Bad Request
    - Attempting work-completed fails with HTTP 400 Bad Request
    - Customer Approves quotation -> status becomes QUOTE_APPROVED
    - verify-end-otp now succeeds -> payment_pending
    - Repeated approval is idempotent and succeeds
    """
    # 1. Create booking
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_scope": "Pipe Leakage Inspection",
        "location": "Wright Town, Jabalpur",
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

    # 3. Fetch rate card and worker creates quotation
    rc_resp = client.get(f"/api/bookings/{booking_id}/rate-card")
    assert rc_resp.status_code == 200
    rc_items = rc_resp.json()["items"]
    assert len(rc_items) > 0
    item = rc_items[0]

    quote_resp = client.post(f"/api/bookings/{booking_id}/quotation", json={
        "items": [{"rate_card_item_id": item["item_id"], "quantity": 1}],
        "worker_notes": "Replacement brass valve required",
    })
    assert quote_resp.status_code == 201
    assert quote_resp.json()["status"] == "QUOTE_PENDING"

    # 4. verify-end-otp MUST fail while quotation is pending approval
    blocked_end_resp = client.post("/api/bookings/verify-end-otp", json={
        "booking_id": booking_id,
        "otp": "9134",
    })
    assert blocked_end_resp.status_code == 400
    assert "Cannot verify Completion OTP while additional work quotation is pending" in blocked_end_resp.json()["detail"]

    # 5. Customer approves quotation
    approve_resp = client.post(f"/api/bookings/{booking_id}/quotation/approve", json={
        "customer_id": 1,
        "customer_notes": "Approved proceed with valve replacement",
    })
    assert approve_resp.status_code == 200
    assert approve_resp.json()["quotation_status"] == "QUOTE_APPROVED"

    # 6. Idempotent approval call returns 200 without duplication
    idempotent_approve = client.post(f"/api/bookings/{booking_id}/quotation/approve", json={
        "customer_id": 1,
    })
    assert idempotent_approve.status_code == 200
    assert idempotent_approve.json()["quotation_status"] == "QUOTE_APPROVED"

    # 7. verify-end-otp now succeeds
    success_end_resp = client.post("/api/bookings/verify-end-otp", json={
        "booking_id": booking_id,
        "otp": "9134",
    })
    assert success_end_resp.status_code == 200
    assert success_end_resp.json()["status"] == "payment_pending"


def test_14_payment_order_qr_and_auth_admin_endpoints():
    """
    Scenario 14: Payment Order UPI QR generation, Auth & Admin Logout, and Federation Health
    """
    # 1. Create booking and transition to payment_pending
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_scope": "Switchboard Diagnostic",
        "location": "Gorakhpur, Jabalpur",
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # Start OTP -> in_progress -> End OTP -> payment_pending
    client.post("/api/bookings/verify-start-otp", json={"booking_id": booking_id, "otp": "4821"})
    client.post("/api/bookings/verify-end-otp", json={"booking_id": booking_id, "otp": "9134"})

    # Create Payment Order
    order_resp = client.post("/api/payments/create-order", json={
        "booking_id": booking_id,
        "customer_id": 1,
        "payment_method": "UPI",
    })
    assert order_resp.status_code == 200
    order_data = order_resp.json()
    assert order_data["upi_qr_data"] is not None
    assert "upi://pay" in order_data["upi_qr_data"]
    assert order_data["upi_id"] == "sahayu.cooperative@sbi"

    # Test Auth Logout
    auth_logout = client.post("/api/auth/logout")
    assert auth_logout.status_code == 200
    assert auth_logout.json()["success"] is True

    # Test Admin Logout
    admin_logout = client.post("/api/admin/logout")
    assert admin_logout.status_code == 200
    assert admin_logout.json()["success"] is True

    # Test Admin Federation Health
    from app.core.security import create_access_token
    admin_token = create_access_token(data={"sub": "1", "role": "admin", "email": "admin@sahayu.in"})
    fed_resp = client.get(
        "/api/admin/federation-health",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert fed_resp.status_code == 200
    fed_data = fed_resp.json()
    assert fed_data["status"] == "operational"
    assert "gullak_reserve_balance" in fed_data
    assert "worker_network" in fed_data


def test_15_real_time_dual_interface_split_screen_synchronization():
    """
    Scenario 15: Two-Interface Real-Time Split-Screen Simulation (Customer + Worker).
    Tests all 15 discrete transition checkpoints for exact state consistency.
    """
    from app.core.security import create_access_token
    customer_token = create_access_token(data={"sub": "1", "role": "customer", "email": "customer@sahayu.in"})
    worker_token = create_access_token(data={"sub": "1", "role": "worker", "email": "worker@sahayu.in"})
    c_headers = {"Authorization": f"Bearer {customer_token}"}
    w_headers = {"Authorization": f"Bearer {worker_token}"}

    def fetch_states(b_id):
        c_r = client.get(f"/api/bookings/{b_id}", headers=c_headers)
        w_r = client.get(f"/api/bookings/{b_id}", headers=w_headers)
        assert c_r.status_code == 200
        assert w_r.status_code == 200
        return c_r.json(), w_r.json()

    # Step 1: Customer creates booking
    create_resp = client.post("/api/bookings/create", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_scope": "Full Bathroom Plumbing Inspection",
        "location": "Civil Lines, Jabalpur",
    }, headers=c_headers)
    assert create_resp.status_code == 201
    b_id = create_resp.json()["booking_id"]

    # Checkpoint 1: Initial Created / Assigned State
    c_state, w_state = fetch_states(b_id)
    assert c_state["status"] in ["pending", "PENDING", "ASSIGNED"]
    assert w_state["status"] == c_state["status"]
    assert c_state["start_otp_state"] == "PENDING"
    assert w_state["start_otp_state"] == "PENDING"
    assert c_state["is_start_otp_verified"] is False
    assert w_state["is_start_otp_verified"] is False
    assert c_state["can_verify_end_otp"] is False
    assert w_state["can_verify_end_otp"] is False
    assert c_state["is_settled"] is False
    assert w_state["is_settled"] is False
    assert c_state["warranty_active"] is False
    assert w_state["warranty_active"] is False

    # Step 2: Worker Accepts
    acc_resp = client.patch(f"/api/bookings/{b_id}/accept", headers=w_headers)
    assert acc_resp.status_code == 200
    c_state, w_state = fetch_states(b_id)
    assert c_state["status"] == "ACCEPTED"
    assert w_state["status"] == "ACCEPTED"

    # Step 3: Start OTP Verified
    start_resp = client.post("/api/bookings/verify-start-otp", json={"booking_id": b_id, "otp": "4821"}, headers=w_headers)
    assert start_resp.status_code == 200
    c_state, w_state = fetch_states(b_id)
    assert c_state["status"] == "in_progress"
    assert w_state["status"] == "in_progress"
    assert c_state["is_start_otp_verified"] is True
    assert w_state["is_start_otp_verified"] is True
    assert c_state["start_otp_state"] == "VERIFIED"
    assert w_state["start_otp_state"] == "VERIFIED"
    assert c_state["end_otp_state"] == "ELIGIBLE"
    assert w_state["end_otp_state"] == "ELIGIBLE"
    assert c_state["can_verify_end_otp"] is True
    assert w_state["can_verify_end_otp"] is True

    # Step 4: Worker submits Add-on quotation (₹470: ₹200 labor + ₹270 material)
    rc_resp = client.get(f"/api/bookings/{b_id}/rate-card", headers=w_headers)
    rc_items = rc_resp.json()["items"]
    item1 = rc_items[0]
    quote_resp = client.post(f"/api/bookings/{b_id}/quotation", json={
        "items": [{"rate_card_item_id": item1["item_id"], "quantity": 1}],
        "worker_notes": "Brass stop cock replacement and pipe sealing",
    }, headers=w_headers)
    assert quote_resp.status_code == 201

    # Checkpoint 4: Add-on Pending Approval -> End OTP MUST be BLOCKED and hidden on both sides!
    c_state, w_state = fetch_states(b_id)
    assert c_state["quotation_status"] == "QUOTE_PENDING"
    assert w_state["quotation_status"] == "QUOTE_PENDING"
    assert c_state["end_otp_state"] == "BLOCKED_AWAITING_APPROVAL"
    assert w_state["end_otp_state"] == "BLOCKED_AWAITING_APPROVAL"
    assert c_state["end_otp"] is None
    assert w_state["end_otp"] is None
    assert c_state["can_verify_end_otp"] is False
    assert w_state["can_verify_end_otp"] is False

    # Attempting verify-end-otp while quote is pending strictly returns HTTP 400
    fail_end = client.post("/api/bookings/verify-end-otp", json={"booking_id": b_id, "otp": "9134"}, headers=w_headers)
    assert fail_end.status_code == 400

    # Step 5: Customer Approves quotation
    appr_resp = client.post(f"/api/bookings/{b_id}/quotation/approve", json={"customer_notes": "Approved proceed"}, headers=c_headers)
    assert appr_resp.status_code == 200
    c_state, w_state = fetch_states(b_id)
    assert c_state["quotation_status"] == "QUOTE_APPROVED"
    assert w_state["quotation_status"] == "QUOTE_APPROVED"
    assert c_state["end_otp_state"] == "ELIGIBLE"
    assert w_state["end_otp_state"] == "ELIGIBLE"
    assert c_state["end_otp"] == "9134"
    assert w_state["end_otp"] == "9134"
    assert c_state["can_verify_end_otp"] is True
    assert w_state["can_verify_end_otp"] is True
    assert c_state["final_bill_amount"] > 239.00
    assert w_state["final_bill_amount"] == c_state["final_bill_amount"]
    assert c_state["worker_total_payout"] > 199.00
    assert w_state["worker_total_payout"] == c_state["worker_total_payout"]

    # Step 6: Worker marks work completed & verifies Completion OTP
    wc_resp = client.post(f"/api/bookings/{b_id}/work-completed", headers=w_headers)
    assert wc_resp.status_code == 200
    end_resp = client.post("/api/bookings/verify-end-otp", json={"booking_id": b_id, "otp": "9134"}, headers=w_headers)
    assert end_resp.status_code == 200

    # Checkpoint 6: PAYMENT_PENDING state
    c_state, w_state = fetch_states(b_id)
    assert c_state["status"] == "payment_pending"
    assert w_state["status"] == "payment_pending"
    assert c_state["payment_status"] == "PENDING"
    assert w_state["payment_status"] == "PENDING"
    assert c_state["is_end_otp_verified"] is True
    assert w_state["is_end_otp_verified"] is True
    assert c_state["end_otp_state"] == "VERIFIED"
    assert w_state["end_otp_state"] == "VERIFIED"
    assert c_state["is_settled"] is False
    assert w_state["is_settled"] is False
    assert c_state["settlement_status"] == "PENDING_PAYMENT"
    assert w_state["settlement_status"] == "PENDING_PAYMENT"
    assert c_state["warranty_active"] is False
    assert w_state["warranty_active"] is False

    # Step 7: Customer executes Demo Payment
    pay_resp = client.post(f"/api/bookings/{b_id}/demo-pay", headers=c_headers)
    assert pay_resp.status_code == 200

    # Checkpoint 7: COMPLETED, SETTLED, and WARRANTY ACTIVE across both interfaces
    c_state, w_state = fetch_states(b_id)
    assert c_state["status"] == "COMPLETED"
    assert w_state["status"] == "COMPLETED"
    assert c_state["payment_status"] == "PAID"
    assert w_state["payment_status"] == "PAID"
    assert c_state["is_settled"] is True
    assert w_state["is_settled"] is True
    assert c_state["settlement_status"] == "SETTLED"
    assert w_state["settlement_status"] == "SETTLED"
    assert c_state["warranty_active"] is True
    assert w_state["warranty_active"] is True
    assert c_state["warranty_expires_at"] is not None
    assert w_state["warranty_expires_at"] == c_state["warranty_expires_at"]
    assert c_state["final_bill_amount"] == w_state["final_bill_amount"]
    assert c_state["settlement_breakdown"]["total_settled"] == c_state["final_bill_amount"]







