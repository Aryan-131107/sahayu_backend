"""
tests/test_auth.py — Test Authentication, JWT Generation, Role Separation & Security
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_customer_registration_success():
    """Customer registration returns valid JWT access token and profile."""
    payload = {
        "name": "Test Customer One",
        "phone": "9998880001",
        "email": "test.customer1@example.com",
        "password": "Password123!",
        "address": "456 Civil Lines",
        "city": "Jabalpur",
        "latitude": 23.1815,
        "longitude": 79.9864,
    }
    resp = client.post("/api/auth/register/customer", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_type"] == "customer"
    assert data["user"]["email"] == "test.customer1@example.com"


def test_customer_registration_duplicate_email():
    """Duplicate email registration is rejected with 409 Conflict."""
    payload = {
        "name": "Duplicate Customer",
        "phone": "9998880002",
        "email": "customer@example.com",  # Already exists from seed
        "password": "Password123!",
    }
    resp = client.post("/api/auth/register/customer", json=payload)
    assert resp.status_code == 409


def test_worker_registration_success():
    """Worker registration with skills returns valid JWT access token and profile."""
    payload = {
        "name": "Test Worker One",
        "phone": "9998880003",
        "email": "test.worker1@example.com",
        "password": "Password123!",
        "experience_years": 4,
        "hourly_rate": 280.0,
        "address": "12 Wright Town",
        "city": "Jabalpur",
        "latitude": 23.1850,
        "longitude": 79.9820,
        "skill_ids": [1, 2],
    }
    resp = client.post("/api/auth/register/worker", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "worker"
    assert data["user"]["name"] == "Test Worker One"


def test_login_demo_customer():
    """Demo customer login with seed credentials."""
    resp = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "customer"
    assert data["user"]["email"] == "customer@example.com"


def test_login_demo_worker():
    """Demo worker login with seed credentials."""
    resp = client.post("/api/auth/login", json={
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
    resp = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "WrongPassword!",
    })
    assert resp.status_code == 401


def test_login_nonexistent_email():
    """Nonexistent email returns 401 Unauthorized."""
    resp = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "Password123!",
    })
    assert resp.status_code == 401


def test_get_me_with_valid_token():
    """GET /api/auth/me returns authenticated profile."""
    # Login first
    login_resp = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
    })
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "customer@example.com"
    assert me_data["role"] == "customer"


def test_get_me_with_invalid_token():
    """GET /api/auth/me with invalid token returns 401."""
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_123"})
    assert resp.status_code == 401
