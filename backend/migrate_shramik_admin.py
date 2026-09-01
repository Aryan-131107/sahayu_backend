"""
migrate_shramik_admin.py — Non-destructive Database Migration for Shramik Verification & Admin Users
Safe for Supabase / PostgreSQL. Preserves all existing tables, foreign keys, and records.
"""
import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


MIGRATION_SQL = """
-- 1. Extend worker_data with Demo Shramik / e-Shram verification fields
ALTER TABLE worker_data ADD COLUMN IF NOT EXISTS shramik_id VARCHAR(50);
ALTER TABLE worker_data ADD COLUMN IF NOT EXISTS skill_certificate VARCHAR(255);
ALTER TABLE worker_data ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) NOT NULL DEFAULT 'VERIFIED';
ALTER TABLE worker_data ADD COLUMN IF NOT EXISTS verification_type VARCHAR(50) DEFAULT 'DEMO_SHRAMIK';
ALTER TABLE worker_data ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;

-- 2. Extend services with is_active flag
ALTER TABLE services ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 3. Create admin_users table
CREATE TABLE IF NOT EXISTS admin_users (
    admin_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create Indexes
CREATE UNIQUE INDEX IF NOT EXISTS ix_worker_data_shramik_id ON worker_data (shramik_id) WHERE shramik_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_worker_data_verification_status ON worker_data (verification_status);
CREATE UNIQUE INDEX IF NOT EXISTS ix_admin_users_email ON admin_users (email);

-- 5. Backfill verification status for existing verified workers
UPDATE worker_data 
SET verification_status = 'VERIFIED', verified_at = CURRENT_TIMESTAMP 
WHERE is_verified = TRUE AND (verification_status IS NULL OR verification_status = 'PENDING');
"""


def run_migration():
    print("=" * 60)
    print("  Sahayu Shramik & Admin Schema Migration")
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
            print("[OK] Added shramik_id, skill_certificate, verification_status, verification_type, verified_at to worker_data.")
            print("[OK] Added is_active to services.")
            print("[OK] Created admin_users table and necessary indexes.")
    except Exception as e:
        print(f"[FAIL] Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
