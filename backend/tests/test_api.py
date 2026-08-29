"""
tests/test_api.py — End-to-End API Integration Test Suite
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────
# 1. Get Workers
# ─────────────────────────────────────────────────────────────────────

def test_get_workers_returns_list():
    """GET /workers should return a list of workers."""
    resp = client.get("/workers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_workers_all_active_by_default():
    """GET /workers should only return active workers by default."""
    resp = client.get("/workers")
    assert resp.status_code == 200
    for worker in resp.json():
        assert worker["is_active"] is True, f"Inactive worker returned: {worker['name']}"


def test_get_worker_by_id():
    """GET /workers/1 should return a specific worker."""
    resp = client.get("/workers/1")
    assert resp.status_code == 200
    data = resp.json()
    assert "worker_id" in data
    assert data["worker_id"] == 1


def test_get_worker_not_found():
    """GET /workers/9999 should return 404."""
    resp = client.get("/workers/9999")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# 2. Get Services
# ─────────────────────────────────────────────────────────────────────

def test_get_services():
    """GET /services should return all services with linked skill info."""
    resp = client.get("/services")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for svc in data:
        assert "skill_id" in svc
        assert "service_name" in svc or "service" in svc


def test_get_service_by_id():
    """GET /services/1 should return a single service."""
    resp = client.get("/services/1")
    assert resp.status_code == 200
    data = resp.json()
    assert "service_id" in data
    assert data["service_id"] == 1


def test_get_service_not_found():
    """GET /services/9999 should return 404."""
    resp = client.get("/services/9999")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# 3. Search Electricians
# ─────────────────────────────────────────────────────────────────────

def test_search_electricians():
    """GET /workers/search?skill=Electrician should return active electricians."""
    resp = client.get("/workers/search?skill=Electrician")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_search_case_insensitive():
    """Search should be case-insensitive."""
    resp1 = client.get("/workers/search?skill=Electrician")
    resp2 = client.get("/workers/search?skill=electrician")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert len(resp1.json()) == len(resp2.json())


def test_search_unknown_skill():
    """Searching for a non-existent skill should return 404."""
    resp = client.get("/workers/search?skill=Astronaut")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# 4. Filter Inactive / Unavailable Workers
# ─────────────────────────────────────────────────────────────────────

def test_recommend_excludes_inactive_workers():
    """Recommendation engine should never include inactive workers."""
    services = client.get("/services").json()
    service_id = services[0]["service_id"]

    resp = client.get(
        f"/workers/recommend?service_id={service_id}&latitude=23.1815&longitude=79.9864"
    )
    assert resp.status_code == 200
    assert "recommendations" in resp.json()
    for rec in resp.json()["recommendations"]:
        # Worker 13 (Sanjay Soni) and Worker 14 (Pappu Lodhi) are inactive
        assert rec["worker_id"] not in [13, 14]


# ─────────────────────────────────────────────────────────────────────
# 5. Recommendation Endpoint
# ─────────────────────────────────────────────────────────────────────

def test_recommendation_endpoint_structure():
    """GET /workers/recommend should return well-structured recommendations."""
    services = client.get("/services").json()
    service_id = services[0]["service_id"]

    resp = client.get(
        f"/workers/recommend?service_id={service_id}&latitude=23.1815&longitude=79.9864"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "recommendations" in body

    if body["recommendations"]:
        rec = body["recommendations"][0]
        required_fields = [
            "worker_id", "name", "experience_years", "is_verified",
            "is_available", "distance_km", "recommendation_score", "relevant_skill"
        ]
        for field in required_fields:
            assert field in rec, f"Missing field '{field}' in recommendation"

        assert 0.0 <= rec["recommendation_score"] <= 1.0
        assert rec["distance_km"] >= 0


def test_recommendation_sorted_by_score():
    """Recommendations must be sorted by score (highest first)."""
    services = client.get("/services").json()
    service_id = services[0]["service_id"]

    resp = client.get(
        f"/workers/recommend?service_id={service_id}&latitude=23.1815&longitude=79.9864"
    )
    recs = resp.json()["recommendations"]
    if len(recs) > 1:
        scores = [r["matching_score"] for r in recs]
        assert scores == sorted(scores, reverse=True), "Recommendations not sorted by score"


def test_recommendation_bad_service():
    """Recommendation with invalid service_id should return 404."""
    resp = client.get("/workers/recommend?service_id=9999&latitude=23.1815&longitude=79.9864")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# 6. Booking Creation & Mismatch Checks
# ─────────────────────────────────────────────────────────────────────

def test_create_booking_success():
    """POST /bookings should create a new PENDING booking."""
    future_date = (date.today() + timedelta(days=60)).isoformat()
    resp = client.post("/bookings", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": future_date,
        "start_time": "14:00:00",
        "amount": 250.00,
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "PENDING"


def test_create_booking_invalid_customer():
    """POST /bookings with non-existent customer_id should return 404."""
    resp = client.post("/bookings", json={
        "customer_id": 9999,
        "worker_id": 1,
        "service_id": 1,
        "amount": 250.00,
    })
    assert resp.status_code == 404


def test_create_booking_wrong_skill():
    """POST /bookings where worker doesn't have the required skill should return 400."""
    # Worker 2 is a Plumber (skill 2), Service 6 is Wall Painting (skill 4 - Painter)
    resp = client.post("/bookings", json={
        "customer_id": 1,
        "worker_id": 2,
        "service_id": 6,
        "amount": 850.00,
    })
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────
# 7. Booking Lifecycle & State Transitions
# ─────────────────────────────────────────────────────────────────────

def test_booking_state_transitions():
    """Full lifecycle test: create booking → accept → start → complete → review."""
    target_date = (date.today() + timedelta(days=65)).isoformat()
    create_resp = client.post("/bookings", json={
        "customer_id": 2,
        "worker_id": 1,
        "service_id": 1,
        "booking_date": target_date,
        "start_time": "15:00:00",
        "amount": 250.00,
    })
    assert create_resp.status_code == 201
    booking_id = create_resp.json()["booking_id"]

    # Accept
    accept_resp = client.patch(f"/bookings/{booking_id}/accept")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"

    # Start
    start_resp = client.patch(f"/bookings/{booking_id}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "IN_PROGRESS"

    # Complete
    complete_resp = client.patch(f"/bookings/{booking_id}/complete")
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "COMPLETED"
    assert complete_resp.json()["payment_status"] == "PAID"

    # Review
    review_resp = client.post("/reviews", json={
        "booking_id": booking_id,
        "customer_id": 2,
        "rating": 4.9,
        "review": "Flawless fan repair and courteous behavior!",
    })
    assert review_resp.status_code == 201
    assert review_resp.json()["rating"] == 4.9


def test_cannot_accept_completed_booking():
    """Cannot re-accept a completed booking."""
    resp = client.patch("/bookings/1/accept")
    assert resp.status_code == 409


def test_cannot_cancel_completed_booking():
    """Cannot cancel a completed booking."""
    resp = client.patch("/bookings/1/cancel")
    assert resp.status_code == 409


# ─────────────────────────────────────────────────────────────────────
# 8. Skills & Health
# ─────────────────────────────────────────────────────────────────────

def test_get_skills():
    """GET /skills should return all skill categories."""
    resp = client.get("/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10
    skill_names = [s["skill_name"] for s in data]
    assert "Electrician" in skill_names
    assert "Plumber" in skill_names


def test_health_check():
    """GET /health should report healthy status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
    assert resp.json()["database"] == "connected"
