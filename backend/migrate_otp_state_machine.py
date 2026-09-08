"""
migrate_otp_state_machine.py — Non-destructive Database Migration for OTP Attempt Tracking & Verification Timestamps
Safe for Supabase / PostgreSQL. Preserves all existing tables, foreign keys, and records.
"""
import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MIGRATION_SQL = """
-- 1. Extend bookings table with attempt tracking and verification timestamp columns
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS start_otp_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS end_otp_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS is_start_otp_locked BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS is_end_otp_locked BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS start_otp_verified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS end_otp_verified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS last_otp_attempt_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS warranty_started_at TIMESTAMP WITH TIME ZONE;

-- 2. Ensure indexes
CREATE INDEX IF NOT EXISTS ix_bookings_is_start_otp_locked ON bookings (is_start_otp_locked);
CREATE INDEX IF NOT EXISTS ix_bookings_is_end_otp_locked ON bookings (is_end_otp_locked);
"""


def run_migration():
    print("=" * 60)
    print("  Sahayu OTP State Machine & Attempt Tracking Schema Migration")
    print("=" * 60)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[FAIL] DATABASE_URL is not set. Please set the DATABASE_URL environment variable.")
        sys.exit(1)

    from app.database import engine

    try:
        with engine.connect() as conn:
            print("[*] Applying non-destructive schema updates...")
            conn.execute(text(MIGRATION_SQL))
            conn.commit()
            print("[OK] Schema migration completed successfully.")
            print("[OK] Extended bookings with start_otp_attempts, end_otp_attempts, is_start_otp_locked, is_end_otp_locked, start_otp_verified_at, end_otp_verified_at, last_otp_attempt_at, warranty_started_at.")
    except Exception as e:
        print(f"[FAIL] Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
