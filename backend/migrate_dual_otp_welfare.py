"""
migrate_dual_otp_welfare.py — Non-destructive Database Migration for Dual-OTP & Cooperative Welfare Ledger
Safe for Supabase / PostgreSQL. Preserves all existing tables, foreign keys, and records.
"""
import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MIGRATION_SQL = """
-- 1. Extend bookings table with Dual-OTP, pricing breakdown, and warranty columns
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS start_otp VARCHAR(6) NOT NULL DEFAULT '4821';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS end_otp VARCHAR(6) NOT NULL DEFAULT '9134';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS worker_payout_amount NUMERIC(10, 2) NOT NULL DEFAULT 199.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS platform_tech_fee NUMERIC(10, 2) NOT NULL DEFAULT 30.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS welfare_pool_fee NUMERIC(10, 2) NOT NULL DEFAULT 10.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS total_amount NUMERIC(10, 2) NOT NULL DEFAULT 239.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS warranty_active BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS warranty_expires_at TIMESTAMP;

-- 2. Create cooperative_welfare_ledger table (Slide 3 Welfare DB)
CREATE TABLE IF NOT EXISTS cooperative_welfare_ledger (
    id SERIAL PRIMARY KEY,
    booking_id INT REFERENCES bookings(booking_id) ON DELETE SET NULL,
    society_id INT NOT NULL DEFAULT 1,
    amount NUMERIC(10, 2) NOT NULL DEFAULT 10.00,
    entry_type VARCHAR(10) NOT NULL DEFAULT 'CREDIT',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create Indexes
CREATE INDEX IF NOT EXISTS ix_cooperative_welfare_ledger_society_id ON cooperative_welfare_ledger (society_id);
CREATE INDEX IF NOT EXISTS ix_cooperative_welfare_ledger_booking_id ON cooperative_welfare_ledger (booking_id);
"""


def run_migration():
    print("=" * 60)
    print("  Sahayu Dual-OTP & Welfare Ledger Schema Migration")
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
            print("[OK] Extended bookings with start_otp, end_otp, worker_payout_amount, platform_tech_fee, welfare_pool_fee, total_amount, warranty_active, warranty_expires_at.")
            print("[OK] Created cooperative_welfare_ledger table and necessary indexes.")
    except Exception as e:
        print(f"[FAIL] Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
