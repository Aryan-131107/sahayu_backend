"""
tests/test_worker_acceptance_matrix.py — Comprehensive Matrix Testing
Covers Scenarios A through O for Real Worker Booking Acceptance, Authorization, State Machine, and Session Persistence.
"""
from datetime import date, timedelta, time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.database import SessionLocal
from app.models import Booking, WorkerData, CustomerData, Service

client = TestClient(app)


def test_scenario_a_worker_a_accepts_assigned_booking():
    """Scenario A: Worker A (Ramesh Patel - Carpenter) accepts their own assigned booking (Service 5)."""
    token_a = create_access_token({"sub": "3", "role": "worker", "email": "ramesh.patel@example.com"})
    headers_a = {"Authorization": f"Bearer {token_a}"}

    create_resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": (date.today() + timedelta(days=50)).isoformat(),
        "start_time": "09:00:00",
        "amount": 250.00,
    })
    assert create_resp.status_code == 201
    b_id = create_resp.json()["booking_id"]

    accept_resp = client.patch(f"/api/bookings/{b_id}/accept", headers=headers_a)
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"


def test_scenario_b_worker_b_accepts_assigned_booking():
    """Scenario B: Worker B (Arvind Gupta - Electrician) accepts their own assigned booking (Service 2)."""
    token_b = create_access_token({"sub": "11", "role": "worker", "email": "arvind.gupta@example.com"})
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 11,
        "service_id": 2,
        "booking_date": (date.today() + timedelta(days=51)).isoformat(),
        "start_time": "10:00:00",
        "amount": 250.00,
    })
    assert create_resp.status_code == 201
    b_id = create_resp.json()["booking_id"]

    accept_resp = client.put(f"/api/bookings/{b_id}/accept", headers=headers_b)
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "ACCEPTED"


def test_scenario_c_multiple_assigned_bookings_same_worker():
    """Scenario C: Same worker accepts multiple distinct assigned bookings on different slots."""
    token_a = create_access_token({"sub": "3", "role": "worker", "email": "ramesh.patel@example.com"})
    headers_a = {"Authorization": f"Bearer {token_a}"}

    b_ids = []
    for hour, day_offset in [(11, 52), (14, 53)]:
        resp = client.post("/api/bookings", json={
            "customer_id": 1,
            "worker_id": 3,
            "service_id": 5,
            "booking_date": (date.today() + timedelta(days=day_offset)).isoformat(),
            "start_time": f"{hour:02d}:00:00",
            "amount": 250.00,
        })
        assert resp.status_code == 201
        b_ids.append(resp.json()["booking_id"])

    for b_id in b_ids:
        acc = client.patch(f"/api/bookings/{b_id}/accept", headers=headers_a)
        assert acc.status_code == 200
        assert acc.json()["status"] == "ACCEPTED"


def test_scenario_d_different_workers_with_different_bookings():
    """Scenario D: Independent workers accept their respective assigned bookings concurrently."""
    token_a = create_access_token({"sub": "3", "role": "worker", "email": "ramesh.patel@example.com"})
    token_b = create_access_token({"sub": "11", "role": "worker", "email": "arvind.gupta@example.com"})

    resp_a = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": (date.today() + timedelta(days=54)).isoformat(),
        "start_time": "12:00:00",
        "amount": 250.00,
    })
    resp_b = client.post("/api/bookings", json={
        "customer_id": 2,
        "worker_id": 11,
        "service_id": 2,
        "booking_date": (date.today() + timedelta(days=54)).isoformat(),
        "start_time": "12:00:00",
        "amount": 250.00,
    })
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    b_id_a = resp_a.json()["booking_id"]
    b_id_b = resp_b.json()["booking_id"]

    acc_a = client.patch(f"/api/bookings/{b_id_a}/accept", headers={"Authorization": f"Bearer {token_a}"})
    acc_b = client.patch(f"/api/bookings/{b_id_b}/accept", headers={"Authorization": f"Bearer {token_b}"})
    assert acc_a.status_code == 200 and acc_a.json()["status"] == "ACCEPTED"
    assert acc_b.status_code == 200 and acc_b.json()["status"] == "ACCEPTED"


def test_scenario_e_cross_worker_acceptance_rejected():
    """Scenario E: Worker B attempts to accept Worker A's assigned booking -> 403 Forbidden."""
    token_b = create_access_token({"sub": "11", "role": "worker", "email": "arvind.gupta@example.com"})

    resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": (date.today() + timedelta(days=55)).isoformat(),
        "start_time": "15:00:00",
        "amount": 250.00,
    })
    assert resp.status_code == 201
    b_id = resp.json()["booking_id"]

    acc = client.patch(f"/api/bookings/{b_id}/accept", headers={"Authorization": f"Bearer {token_b}"})
    assert acc.status_code == 403
    assert "assigned to another worker" in acc.json()["detail"]


def test_scenario_f_already_accepted_booking_idempotent():
    """Scenario F: Repeating accept on already ACCEPTED booking returns 200 OK idempotently."""
    token_a = create_access_token({"sub": "3", "role": "worker", "email": "ramesh.patel@example.com"})
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": (date.today() + timedelta(days=56)).isoformat(),
        "start_time": "16:00:00",
        "amount": 250.00,
    })
    assert resp.status_code == 201
    b_id = resp.json()["booking_id"]

    acc1 = client.patch(f"/api/bookings/{b_id}/accept", headers=headers)
    assert acc1.status_code == 200
    assert acc1.json()["status"] == "ACCEPTED"

    acc2 = client.patch(f"/api/bookings/{b_id}/accept", headers=headers)
    assert acc2.status_code == 200
    assert acc2.json()["status"] == "ACCEPTED"


def test_scenario_g_completed_booking_cannot_be_accepted():
    """Scenario G: Attempting to accept a COMPLETED booking is rejected (409 Conflict)."""
    token_a = create_access_token({"sub": "3", "role": "worker", "email": "ramesh.patel@example.com"})
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 3,
        "service_id": 5,
        "booking_date": (date.today() + timedelta(days=57)).isoformat(),
        "start_time": "17:00:00",
        "amount": 250.00,
    })
    assert resp.status_code == 201
    b_id = resp.json()["booking_id"]
    client.patch(f"/api/bookings/{b_id}/accept", headers=headers)
    client.patch(f"/api/bookings/{b_id}/start", headers=headers)
    client.patch(f"/api/bookings/{b_id}/complete", headers=headers)

    acc = client.patch(f"/api/bookings/{b_id}/accept", headers=headers)
    assert acc.status_code == 409
    assert "Cannot transition" in acc.json()["detail"]


def test_scenario_h_invalid_booking_id():
    """Scenario H: Acceptance on non-existent booking returns 404 Not Found."""
    token_a = create_access_token({"sub": "3", "role": "worker", "email": "ramesh.patel@example.com"})
    acc = client.patch("/api/bookings/99999999/accept", headers={"Authorization": f"Bearer {token_a}"})
    assert acc.status_code == 404
    assert "not found" in acc.json()["detail"].lower()


def test_scenario_i_unauthenticated_acceptance():
    """Scenario I: Unauthenticated request to accept without token allows fallback for local testing."""
    resp = client.post("/api/bookings", json={
        "customer_id": 1,
        "worker_id": 1,
        "service_id": 2,
        "booking_date": (date.today() + timedelta(days=58)).isoformat(),
        "start_time": "18:00:00",
        "amount": 250.00,
    })
    assert resp.status_code == 201
    b_id = resp.json()["booking_id"]

    acc = client.patch(f"/api/bookings/{b_id}/accept")
    assert acc.status_code == 200
    assert acc.json()["status"] == "ACCEPTED"


def test_scenario_j_expired_session_rejected():
    """Scenario J: Expired JWT token is rejected with 401 Unauthorized."""
    expired_token = create_access_token(
        {"sub": "3", "role": "worker", "email": "ramesh.patel@example.com"},
        expires_delta=timedelta(seconds=-10),
    )
    resp = client.get("/api/bookings/worker/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "Invalid or expired token" in resp.json()["detail"]


def test_scenario_k_login_and_token_validation():
    """Scenario K: Login returns valid JWT and user profile."""
    resp = client.post("/api/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "worker"
    assert data["user"]["id"] == 1


def test_scenario_l_session_restoration():
    """Scenario L: Stored access token can be used repeatedly to access protected feeds."""
    login_resp = client.post("/api/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # First call (representing initial load)
    r1 = client.get("/api/bookings/worker/me", headers=headers)
    assert r1.status_code == 200

    # Second call (representing session restoration on app reopen / reload)
    r2 = client.get("/api/bookings/worker/me", headers=headers)
    assert r2.status_code == 200
    assert len(r1.json()) == len(r2.json())


def test_scenario_m_logout_protected_route_rejected():
    """Scenario M: Request without Bearer token to worker-only endpoint is rejected."""
    resp = client.get("/api/bookings/worker/me")
    assert resp.status_code == 401


def test_scenario_n_worker_registration():
    """Scenario N: Worker registration with skills, phone, and e-Shram metadata."""
    with SessionLocal() as db:
        db.query(WorkerData).filter(WorkerData.email == "matrix.worker@example.com").delete()
        db.commit()

    payload = {
        "name": "Matrix Test Worker",
        "phone": "9876543299",
        "email": "matrix.worker@example.com",
        "password": "Password123!",
        "role": "worker",
        "experience_years": 5,
        "hourly_rate": 300.0,
        "skill_ids": [1],
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "worker"
    assert data["user"]["email"] == "matrix.worker@example.com"


def test_scenario_o_no_http_500_on_valid_operations():
    """Scenario O: Health and listing endpoints execute cleanly without internal server errors."""
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    r_workers = client.get("/api/workers")
    assert r_workers.status_code == 200

    r_services = client.get("/api/services")
    assert r_services.status_code == 200
