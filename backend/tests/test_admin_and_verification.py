"""
tests/test_admin_and_verification.py — Tests for Demo Shramik Verification & Admin Dashboard
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import WorkerData, AdminUser, Service

client = TestClient(app)


def get_admin_token() -> str:
    """Helper to obtain admin JWT token."""
    resp = client.post("/auth/login", json={
        "email": "admin@example.com",
        "password": "Password123!",
        "role": "admin",
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]


def get_worker_token() -> str:
    """Helper to obtain worker JWT token."""
    resp = client.post("/auth/login", json={
        "email": "worker@example.com",
        "password": "Password123!",
        "role": "worker",
    })
    assert resp.status_code == 200, f"Worker login failed: {resp.text}"
    return resp.json()["access_token"]


def get_customer_token() -> str:
    """Helper to obtain customer JWT token."""
    resp = client.post("/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!",
        "role": "customer",
    })
    assert resp.status_code == 200, f"Customer login failed: {resp.text}"
    return resp.json()["access_token"]


# ─────────────────────────────────────────────────────────
# 1. ADMIN AUTHENTICATION & RBAC TESTS
# ─────────────────────────────────────────────────────────

def test_admin_login_success():
    """POST /auth/login with admin credentials returns admin JWT."""
    resp = client.post("/auth/login", json={
        "email": "admin@example.com",
        "password": "Password123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user_type"] == "admin"
    assert data["user"]["role"] == "admin"


def test_admin_stats_authorized():
    """GET /admin/stats with Admin token returns platform statistics."""
    token = get_admin_token()
    resp = client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_workers" in data
    assert "verified_workers" in data
    assert "pending_workers" in data
    assert "total_customers" in data
    assert "total_bookings" in data
    assert "total_customer_payments" in data
    assert "total_worker_earnings" in data
    assert "total_platform_fees" in data
    assert data["total_workers"] >= 20


def test_admin_endpoints_unauthorized_without_token():
    """GET /admin/stats without token returns 401 Unauthorized."""
    resp = client.get("/admin/stats")
    assert resp.status_code == 401


def test_admin_endpoints_forbidden_for_customer():
    """GET /admin/stats with Customer token returns 403 Forbidden."""
    token = get_customer_token()
    resp = client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_endpoints_forbidden_for_worker():
    """GET /admin/stats with Worker token returns 403 Forbidden."""
    token = get_worker_token()
    resp = client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────
# 2. WORKER SHRAMIK VERIFICATION LIFECYCLE TESTS
# ─────────────────────────────────────────────────────────

def test_worker_submit_verification():
    """POST /workers/verify submits worker for Shramik verification."""
    # Reset worker 4 (Dinesh Yadav) verification state
    with SessionLocal() as db:
        w = db.get(WorkerData, 4)
        if w:
            w.verification_status = "PENDING"
            w.is_verified = False
            w.shramik_id = None
            db.commit()

    payload = {
        "worker_id": 4,
        "shramik_id": "SHR-MP-2026-TEST-44",
        "skill": "Painter",
        "skill_certificate": "CERT-PAINT-2024",
        "verification_type": "DEMO_SHRAMIK",
    }
    resp = client.post("/workers/verify", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["worker_id"] == 4
    assert data["shramik_id"] == "SHR-MP-2026-TEST-44"
    assert data["verification_status"] == "PENDING"
    assert data["is_verified"] is False


def test_worker_submit_duplicate_shramik_rejected():
    """POST /workers/verify with existing Shramik ID returns 409 Conflict."""
    payload = {
        "worker_id": 4,
        "shramik_id": "SHR-MP-2026-1001",  # Already assigned to Worker 1
    }
    resp = client.post("/workers/verify", json=payload)
    assert resp.status_code == 409


def test_get_worker_verification_status():
    """GET /workers/{id}/verification returns current verification status."""
    resp = client.get("/workers/1/verification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["worker_id"] == 1
    assert data["verification_status"] == "VERIFIED"
    assert data["is_verified"] is True


def test_admin_get_pending_verifications():
    """GET /admin/verifications lists workers with PENDING status."""
    token = get_admin_token()
    resp = client.get("/admin/verifications", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    workers = resp.json()
    assert isinstance(workers, list)
    for w in workers:
        assert w["verification_status"] == "PENDING"


def test_admin_verify_worker():
    """PATCH /admin/workers/{id}/verify marks worker as VERIFIED."""
    token = get_admin_token()
    resp = client.patch("/admin/workers/4/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["worker_id"] == 4
    assert data["verification_status"] == "VERIFIED"
    assert data["is_verified"] is True
    assert data["verified_at"] is not None


def test_admin_reject_worker():
    """PATCH /admin/workers/{id}/reject marks worker as REJECTED."""
    token = get_admin_token()
    resp = client.patch(
        "/admin/workers/4/reject",
        json={"rejection_reason": "Incomplete trade certificate"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["worker_id"] == 4
    assert data["verification_status"] == "REJECTED"
    assert data["is_verified"] is False


# ─────────────────────────────────────────────────────────
# 3. ADMIN WORKER, BOOKINGS, PAYMENTS, SERVICES, REVIEWS
# ─────────────────────────────────────────────────────────

def test_admin_get_workers_with_filters():
    """GET /admin/workers supports search and filtering."""
    token = get_admin_token()
    # All workers
    resp = client.get("/admin/workers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 20

    # Filter by verified
    resp_v = client.get("/admin/workers?verification_status=VERIFIED", headers={"Authorization": f"Bearer {token}"})
    assert resp_v.status_code == 200
    for w in resp_v.json():
        assert w["verification_status"] == "VERIFIED"

    # Search
    resp_s = client.get("/admin/workers?search=Suresh", headers={"Authorization": f"Bearer {token}"})
    assert resp_s.status_code == 200
    assert len(resp_s.json()) >= 1


def test_admin_update_worker_status():
    """PATCH /admin/workers/{id}/status toggles active flag."""
    token = get_admin_token()
    resp = client.patch(
        "/admin/workers/2/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Restore
    client.patch(
        "/admin/workers/2/status",
        json={"is_active": True},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_admin_get_bookings_with_payment_breakdown():
    """GET /admin/bookings returns bookings with exact payment breakdown."""
    token = get_admin_token()
    resp = client.get("/admin/bookings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    bookings = resp.json()
    assert len(bookings) > 0
    first = bookings[0]
    assert "payment_breakdown" in first
    pb = first["payment_breakdown"]
    # Check invariant: Customer Paid = Platform Fee + Worker Earnings
    assert round(pb["platform_fee"] + pb["worker_earnings"], 2) == round(pb["customer_paid_amount"], 2)
    assert pb["platform_fee_percent"] == 10.0


def test_admin_get_payments_history():
    """GET /admin/payments returns full payment transaction history."""
    token = get_admin_token()
    resp = client.get("/admin/payments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    payments = resp.json()
    assert isinstance(payments, list)
    if payments:
        p = payments[0]
        assert "customer_paid_amount" in p
        assert "platform_fee" in p
        assert "worker_earnings" in p


def test_admin_services_crud():
    """Admin can view, create, and update service catalog."""
    token = get_admin_token()

    # 1. View all services
    resp_list = client.get("/admin/services", headers={"Authorization": f"Bearer {token}"})
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 12

    # 2. Create service
    create_payload = {
        "service_name": "Solar Inverter Maintenance",
        "description": "Solar panel and hybrid inverter health checkup.",
        "category": "Electrical",
        "base_price": 550.00,
        "estimated_duration": 90,
        "skill_id": 1,
    }
    resp_create = client.post("/admin/services", json=create_payload, headers={"Authorization": f"Bearer {token}"})
    assert resp_create.status_code == 201
    svc_id = resp_create.json()["service_id"]

    # 3. Update service
    update_payload = {
        "base_price": 600.00,
        "description": "Updated solar inverter checkup with battery test.",
        "is_active": True,
    }
    resp_update = client.patch(f"/admin/services/{svc_id}", json=update_payload, headers={"Authorization": f"Bearer {token}"})
    assert resp_update.status_code == 200
    assert resp_update.json()["base_price"] == 600.00


def test_admin_get_reviews():
    """GET /admin/reviews lists platform reviews."""
    token = get_admin_token()
    resp = client.get("/admin/reviews", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    reviews = resp.json()
    assert isinstance(reviews, list)
    if reviews:
        r = reviews[0]
        assert "rating" in r
        assert "review" in r
        assert "worker_name" in r
