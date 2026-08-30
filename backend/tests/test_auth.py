"""
tests/test_auth.py — Test Authentication, JWT Generation, Role Separation & Security
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_unified_register_customer_success():
    """POST /auth/register creates customer and returns valid JWT."""
    from app.database import SessionLocal
    from app.models import CustomerData
    with SessionLocal() as db:
        db.query(CustomerData).filter(CustomerData.email == "unified.customer@example.com").delete()
        db.commit()

    payload = {
        "name": "Unified Customer",
        "phone": "9998880010",
        "email": "unified.customer@example.com",
        "password": "Password123!",
        "role": "customer",
        "address": "789 Napier Town",
        "city": "Jabalpur",
    }
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "customer"
    assert data["user"]["email"] == "unified.customer@example.com"


def test_unified_register_worker_success():
    """POST /auth/register creates worker with skills and returns valid JWT."""
    from app.database import SessionLocal
    from app.models import WorkerData
    with SessionLocal() as db:
        db.query(WorkerData).filter(WorkerData.email == "unified.worker@example.com").delete()
        db.commit()

    payload = {
        "name": "Unified Worker",
        "phone": "9998880011",
        "email": "unified.worker@example.com",
        "password": "Password123!",
        "role": "worker",
        "experience_years": 7,
        "hourly_rate": 320.0,
        "skill_ids": [1],
    }
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "worker"
    assert data["user"]["email"] == "unified.worker@example.com"


def test_customer_registration_duplicate_email():
    """Duplicate email registration is rejected with 409 Conflict."""
    payload = {
        "name": "Duplicate Customer",
        "phone": "9998880002",
        "email": "customer@example.com",  # Already exists from seed
        "password": "Password123!",
    }
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409


def test_login_demo_customer():
    """Demo customer login at /auth/login."""
    resp = client.post("/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "customer"
    assert data["user"]["email"] == "customer@example.com"


def test_login_demo_worker():
    """Demo worker login at /auth/login."""
    resp = client.post("/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "worker"
    assert data["user"]["email"] == "worker@example.com"


def test_login_invalid_password():
    """Invalid password returns 401 Unauthorized."""
    resp = client.post("/auth/login", json={
        "email": "customer@example.com",
        "password": "WrongPassword!",
    })
    assert resp.status_code == 401


def test_login_nonexistent_email():
    """Nonexistent email returns 401 Unauthorized."""
    resp = client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "Password123!",
    })
    assert resp.status_code == 401


def test_get_auth_me():
    """GET /auth/me returns authenticated user details."""
    login_resp = client.post("/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "customer@example.com"
    assert me_data["role"] == "customer"


def test_get_customers_me():
    """GET /customers/me returns authenticated customer record."""
    login_resp = client.post("/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/customers/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "customer@example.com"
    assert data["customer_id"] == 1


def test_get_workers_me():
    """GET /workers/me returns authenticated worker record."""
    login_resp = client.post("/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/workers/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "worker@example.com"
    assert data["worker_id"] == 1
    assert "skills" in data


def test_worker_calling_customers_me_forbidden():
    """Worker token cannot call /customers/me (403 Forbidden)."""
    login_resp = client.post("/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/customers/me", headers=headers)
    assert resp.status_code == 403


def test_customer_calling_workers_me_forbidden():
    """Customer token cannot call /workers/me (403 Forbidden)."""
    login_resp = client.post("/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/workers/me", headers=headers)
    assert resp.status_code == 403
