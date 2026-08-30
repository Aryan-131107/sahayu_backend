"""
tests/conftest.py — Pytest configuration and cleanup fixtures for Sahayu backend tests.
"""
import pytest
from datetime import date, timedelta
from app.database import SessionLocal
from app.models import Booking, RatingReview, CustomerData, WorkerData

@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Clean up dynamic test data created during test runs before/after each test."""
    with SessionLocal() as db:
        # Remove bookings in the future created by tests
        tomorrow = date.today() + timedelta(days=1)
        future_bookings = db.query(Booking).filter(Booking.booking_date >= tomorrow).all()
        for b in future_bookings:
            db.query(RatingReview).filter(RatingReview.booking_id == b.booking_id).delete()
            db.delete(b)
        db.commit()
    yield
    with SessionLocal() as db:
        tomorrow = date.today() + timedelta(days=1)
        future_bookings = db.query(Booking).filter(Booking.booking_date >= tomorrow).all()
        for b in future_bookings:
            db.query(RatingReview).filter(RatingReview.booking_id == b.booking_id).delete()
            db.delete(b)
        db.commit()
