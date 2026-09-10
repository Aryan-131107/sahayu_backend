"""
migrate_quotation_payment.py — Non-destructive Database Migration for Rate Cards, Quotations, and Payment Records
Safe for Supabase / PostgreSQL. Preserves all existing tables, foreign keys, and records.
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

MIGRATION_SQL = """
-- 1. Create rate_card_items table if not exists
CREATE TABLE IF NOT EXISTS rate_card_items (
    item_id SERIAL PRIMARY KEY,
    skill_id INT NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    service_id INT REFERENCES services(service_id) ON DELETE SET NULL,
    item_name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'LABOR',
    unit_rate NUMERIC(10, 2) NOT NULL,
    unit VARCHAR(30) NOT NULL DEFAULT 'unit',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rate_card_items_skill_id ON rate_card_items (skill_id);
CREATE INDEX IF NOT EXISTS ix_rate_card_items_service_id ON rate_card_items (service_id);

-- 2. Create quotations table if not exists
CREATE TABLE IF NOT EXISTS quotations (
    quotation_id SERIAL PRIMARY KEY,
    booking_id INT NOT NULL REFERENCES bookings(booking_id) ON DELETE CASCADE,
    worker_id INT NOT NULL REFERENCES worker_data(worker_id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    additional_labor_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    additional_material_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    total_additional_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    worker_notes TEXT,
    customer_notes TEXT,
    submitted_at TIMESTAMP WITH TIME ZONE,
    approved_at TIMESTAMP WITH TIME ZONE,
    rejected_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_quotations_booking_id ON quotations (booking_id);
CREATE INDEX IF NOT EXISTS ix_quotations_status ON quotations (status);

-- 3. Create quotation_items table if not exists
CREATE TABLE IF NOT EXISTS quotation_items (
    item_id SERIAL PRIMARY KEY,
    quotation_id INT NOT NULL REFERENCES quotations(quotation_id) ON DELETE CASCADE,
    rate_card_item_id INT NOT NULL REFERENCES rate_card_items(item_id) ON DELETE RESTRICT,
    item_name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'LABOR',
    unit_rate NUMERIC(10, 2) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    total_amount NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_quotation_items_quotation_id ON quotation_items (quotation_id);
CREATE INDEX IF NOT EXISTS ix_quotation_items_rate_card_item_id ON quotation_items (rate_card_item_id);

-- 4. Create payment_records table if not exists
CREATE TABLE IF NOT EXISTS payment_records (
    payment_id SERIAL PRIMARY KEY,
    booking_id INT NOT NULL REFERENCES bookings(booking_id) ON DELETE RESTRICT,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    payment_reference VARCHAR(100),
    amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    payment_method VARCHAR(50) NOT NULL DEFAULT 'DEMO_PAY',
    status VARCHAR(30) NOT NULL DEFAULT 'SUCCESS',
    is_demo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_payment_records_booking_id ON payment_records (booking_id);
CREATE INDEX IF NOT EXISTS ix_payment_records_order_id ON payment_records (order_id);
CREATE INDEX IF NOT EXISTS ix_payment_records_status ON payment_records (status);

-- 5. Extend bookings table with quotation and payment columns
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS additional_service_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS material_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS final_amount NUMERIC(10, 2);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS quotation_status VARCHAR(30) NOT NULL DEFAULT 'NONE';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS customer_approved_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS work_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(100);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS payment_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS settled_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS ix_bookings_quotation_status ON bookings (quotation_status);
CREATE INDEX IF NOT EXISTS ix_bookings_payment_reference ON bookings (payment_reference);
"""


def run_migration():
    print("=" * 60)
    print("  Sahayu Rate Cards, Quotations & Payment Schema Migration")
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
            print("[OK] Created rate_card_items, quotations, quotation_items, payment_records tables.")
            print("[OK] Extended bookings with quotation, approval, completion, and settlement columns.")
    except Exception as e:
        print(f"[FAIL] Migration error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
