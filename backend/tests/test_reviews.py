"""
tests/test_reviews.py — Review Integrity, 1-to-1 Constraints & Rating Recalculation
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_review_creation_on_completed_booking():
    """Create a new booking, complete it, and successfully post a review."""
    # 1. Create booking
    b_resp = client.post("/api/bookings", json={
        "customer_id": 2,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": (date.today() + timedelta(days=40)).isoformat(),
        "start_time": "16:00:00",
        "amount": 250.00,
    })
    assert b_resp.status_code == 201
    booking_id = b_resp.json()["booking_id"]

    # 2. Advance to completed
    client.patch(f"/api/bookings/{booking_id}/accept")
    client.patch(f"/api/bookings/{booking_id}/start")
    client.patch(f"/api/bookings/{booking_id}/complete")

    # 3. Post review
    rev_resp = client.post("/api/reviews", json={
        "booking_id": booking_id,
        "customer_id": 2,
        "rating": 4.8,
        "review": "Very thorough diagnostics and prompt fan repair.",
    })
    assert rev_resp.status_code == 201
    data = rev_resp.json()
    assert data["rating"] == 4.8
    assert data["booking_id"] == booking_id


def test_review_rejected_for_non_completed_booking():
    """Reviews are strictly rejected for bookings not in COMPLETED state."""
    # Create PENDING booking
    b_resp = client.post("/api/bookings", json={
        "customer_id": 2,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": (date.today() + timedelta(days=45)).isoformat(),
        "start_time": "12:00:00",
        "amount": 250.00,
    })
    assert b_resp.status_code == 201
    booking_id = b_resp.json()["booking_id"]

    rev_resp = client.post("/api/reviews", json={
        "booking_id": booking_id,
        "customer_id": 2,
        "rating": 5.0,
        "review": "Premature review",
    })
    assert rev_resp.status_code == 400
    assert "COMPLETED" in rev_resp.json()["detail"]


def test_review_duplicate_rejected():
    """1-to-1 Constraint: Prohibit duplicate reviews for the same booking."""
    # Booking 1 is already reviewed in seed data
    rev_resp = client.post("/api/reviews", json={
        "booking_id": 1,
        "customer_id": 1,
        "rating": 4.0,
        "review": "Duplicate review attempt",
    })
    assert rev_resp.status_code == 409
    assert "already" in rev_resp.json()["detail"].lower()


def test_review_wrong_customer_rejected():
    """Reviews can only be submitted by the customer who created the booking."""
    # Booking 1 belongs to Customer 1, attempt review by Customer 2
    # Create a fresh completed booking for Customer 1
    b_resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": (date.today() + timedelta(days=50)).isoformat(),
        "start_time": "14:00:00",
        "amount": 250.00,
    })
    booking_id = b_resp.json()["booking_id"]
    client.patch(f"/api/bookings/{booking_id}/accept")
    client.patch(f"/api/bookings/{booking_id}/start")
    client.patch(f"/api/bookings/{booking_id}/complete")

    # Customer 2 attempts review
    rev_resp = client.post("/api/reviews", json={
        "booking_id": booking_id,
        "customer_id": 2,  # Wrong customer!
        "rating": 5.0,
        "review": "Unauthorized review",
    })
    assert rev_resp.status_code == 403


def test_worker_reviews_average_recalculated():
    """GET /workers/{worker_id}/reviews computes and returns average rating."""
    resp = client.get("/workers/1/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert "worker_id" in data
    assert "average_rating" in data
    assert "total_reviews" in data
    assert data["total_reviews"] > 0
    assert 1.0 <= data["average_rating"] <= 5.0
