"""
tests/test_bookings.py — Booking Lifecycle, Double Booking Guard & State Machine Tests
"""
from datetime import date, timedelta, time
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_booking_success():
    """Create a new pending booking with valid skill match."""
    # Worker 1 is an Electrician (skill_id 1), Service 1 requires Electrician
    future_date = (date.today() + timedelta(days=15)).isoformat()
    payload = {
        "customer_id": 1,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": future_date,
        "start_time": "14:00:00",
        "address": "123 Civil Lines",
        "description": "Fan repair",
        "amount": 250.00,
    }
    resp = client.post("/api/bookings", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["payment_status"] == "PENDING"
    assert data["amount"] == 250.00


def test_double_booking_guard():
    """Double Booking Guard: Rejects overlapping booking requests for the same worker."""
    future_date = (date.today() + timedelta(days=20)).isoformat()
    slot_time = "10:00:00"

    # First booking on this slot
    payload1 = {
        "customer_id": 1,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": future_date,
        "start_time": slot_time,
        "amount": 250.00,
    }
    resp1 = client.post("/api/bookings", json=payload1)
    assert resp1.status_code == 201

    # Second booking for SAME worker on SAME date & time slot -> MUST FAIL WITH 409
    payload2 = {
        "customer_id": 2,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": future_date,
        "start_time": slot_time,
        "amount": 250.00,
    }
    resp2 = client.post("/api/bookings", json=payload2)
    assert resp2.status_code == 409
    assert "already booked" in resp2.json()["detail"] or "Double booking" in resp2.json()["detail"]


def test_booking_skill_mismatch_rejected():
    """Reject booking when worker does not possess required skill for service."""
    # Worker 2 is a Plumber (skill 2), Service 6 requires Painter (skill 4)
    payload = {
        "customer_id": 1,
        "worker_id": 2,
        "service_id": 6,  # Interior Room Wall Painting (Painter)
        "amount": 850.00,
    }
    resp = client.post("/api/bookings", json=payload)
    assert resp.status_code == 400
    assert "skill" in resp.json()["detail"].lower()


def test_booking_full_lifecycle_and_side_effects():
    """
    Test full state lifecycle:
    PENDING → ACCEPTED (locks availability) → IN_PROGRESS → COMPLETED (frees availability & marks PAID)
    """
    target_date = (date.today() + timedelta(days=25)).isoformat()
    # Create booking for Worker 3 (Carpenter, service 5)
    create_resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": target_date,
        "start_time": "09:00:00",
        "amount": 450.00,
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # 1. Accept
    accept_resp = client.patch(f"/api/bookings/{booking_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    # 2. Start
    start_resp = client.patch(f"/api/bookings/{booking_id}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "IN_PROGRESS"

    # 3. Complete
    complete_resp = client.patch(f"/api/bookings/{booking_id}/complete")
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "COMPLETED"
    assert complete_resp.json()["payment_status"] == "PAID"


def test_booking_rejection_flow():
    """Worker rejects PENDING booking."""
    target_date = (date.today() + timedelta(days=30)).isoformat()
    create_resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": target_date,
        "start_time": "11:00:00",
        "amount": 450.00,
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    reject_resp = client.patch(f"/api/bookings/{booking_id}/reject")
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"


def test_booking_cancellation_flow():
    """Customer cancels PENDING booking."""
    target_date = (date.today() + timedelta(days=35)).isoformat()
    create_resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": target_date,
        "start_time": "15:00:00",
        "amount": 450.00,
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    cancel_resp = client.patch(f"/api/bookings/{booking_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


def test_invalid_state_transition_from_completed():
    """Cannot accept or cancel a COMPLETED booking."""
    # Booking 1 is COMPLETED from seed data
    resp = client.patch("/api/bookings/1/accept")
    assert resp.status_code == 409
    assert "Cannot transition" in resp.json()["detail"]
