"""
tests/test_security_guards.py — Authorization Guards & Cross-Account Protection (401/403)
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_protected_route_missing_token():
    """Unauthenticated call to protected route returns 401 Unauthorized."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_customer_tampering_other_profile_forbidden():
    """Customer cannot modify another customer's profile (403 Forbidden)."""
    # Login as Customer 1
    login_resp = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Customer 1 ID is 1. Attempt to update Customer 2 profile
    update_resp = client.put(
        "/api/customers/2",
        json={"name": "Hacked Name"},
        headers=headers,
    )
    assert update_resp.status_code == 403


def test_customer_viewing_other_booking_history_forbidden():
    """Customer cannot view another customer's booking history (403 Forbidden)."""
    login_resp = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/bookings/customer/2", headers=headers)
    assert resp.status_code == 403


def test_worker_tampering_other_worker_profile_forbidden():
    """Worker cannot modify another worker's profile (403 Forbidden)."""
    # Login as Worker 1
    login_resp = client.post("/api/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Worker 1 ID is 1. Attempt to modify Worker 2 profile
    resp = client.put(
        "/api/workers/2",
        json={"hourly_rate": 999.0},
        headers=headers,
    )
    assert resp.status_code == 403


def test_worker_tampering_other_worker_availability_forbidden():
    """Worker cannot modify another worker's availability (403 Forbidden)."""
    login_resp = client.post("/api/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.patch(
        "/api/workers/2/availability",
        json={"is_available": False},
        headers=headers,
    )
    assert resp.status_code == 403
