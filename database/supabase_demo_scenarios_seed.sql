-- =============================================================================
-- SAHAYU — Supabase Demo Scenarios & State Machine Override SQL Script
-- Problem Statement: SIH 2026 - PS26089 (Cooperative Gig Services Platform)
--
-- PURPOSE:
-- 1. Drops any restrictive terminal check constraints on bookings.status
-- 2. Ensures all required columns, foreign keys, and indexes exist
-- 3. Upserts master Customers, Skills, Workers (Shramik verified), and Services
-- 4. Seeds/Resets 5 canonical Demo Booking Scenarios (#SH-0101 to #SH-0105 & #SH-0058)
--    with clean ASSIGNED status, PINs (4821 / 9134), ₹239 base breakdown, and UNPAID.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Schema Updates & Dropping Restrictive Constraints
-- -----------------------------------------------------------------------------
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS start_otp VARCHAR(6) NOT NULL DEFAULT '4821';
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS end_otp VARCHAR(6) NOT NULL DEFAULT '9134';
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS start_otp_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS end_otp_attempts INT NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS is_start_otp_locked BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS is_end_otp_locked BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS start_otp_verified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS end_otp_verified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS last_otp_attempt_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS worker_payout_amount NUMERIC(10, 2) NOT NULL DEFAULT 199.00;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS platform_tech_fee NUMERIC(10, 2) NOT NULL DEFAULT 30.00;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS welfare_pool_fee NUMERIC(10, 2) NOT NULL DEFAULT 10.00;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS total_amount NUMERIC(10, 2) NOT NULL DEFAULT 239.00;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS additional_service_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS material_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS final_amount NUMERIC(10, 2) NOT NULL DEFAULT 239.00;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS quotation_status VARCHAR(30) NOT NULL DEFAULT 'NONE';
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS customer_approved_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS work_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(100);
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS payment_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS settled_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS warranty_active BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS warranty_started_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS warranty_expires_at TIMESTAMP WITH TIME ZONE;

-- Drop any restrictive check constraints on bookings status
ALTER TABLE IF EXISTS bookings DROP CONSTRAINT IF EXISTS chk_bookings_status;
ALTER TABLE IF EXISTS bookings DROP CONSTRAINT IF EXISTS bookings_status_check;
ALTER TABLE IF EXISTS bookings DROP CONSTRAINT IF EXISTS chk_booking_status;

-- -----------------------------------------------------------------------------
-- 2. Upsert Master Skills
-- -----------------------------------------------------------------------------
INSERT INTO skills (skill_id, skill_name, description) VALUES
  (1, 'Electrician', 'Ceiling fans, switchboards, wiring, MCB breakers, and electrical appliances'),
  (2, 'Plumber', 'Pipe leaks, taps, drain unclogging, flush tanks, and sanitary fittings'),
  (3, 'Gardener', 'Lawn mowing, hedge trimming, weeding, pruning, and garden upkeep'),
  (4, 'Carpenter', 'Door hinges, locks, wooden furniture repairs, and cabinetry'),
  (5, 'AC Technician', 'Split AC deep cleaning, foam jet service, and gas leak inspection')
ON CONFLICT (skill_id) DO UPDATE SET
  skill_name = EXCLUDED.skill_name,
  description = EXCLUDED.description;

-- -----------------------------------------------------------------------------
-- 3. Upsert Master Customers
-- -----------------------------------------------------------------------------
INSERT INTO customer_data (customer_id, name, phone, email, address, city, latitude, longitude) VALUES
  (1, 'Pooja Sharma', '9876543299', 'pooja.sharma@example.com', 'Civil Lines, Jabalpur', 'Jabalpur', 23.181500, 79.986400),
  (2, 'Anand Verma', '9876543210', 'anand.verma@example.com', 'Vijay Nagar, Jabalpur', 'Jabalpur', 23.181500, 79.986400),
  (3, 'Dr. Kavita Jain', '9876543211', 'kavita.jain@example.com', 'Wright Town, Jabalpur', 'Jabalpur', 23.185000, 79.982000),
  (4, 'Sunil Tiwari', '9876543217', 'sunil.tiwari@example.com', 'Napier Town, Jabalpur', 'Jabalpur', 23.190000, 79.980000),
  (5, 'Meera Singhania', '9876543214', 'meera.singhania@example.com', 'Gorakhpur, Jabalpur', 'Jabalpur', 23.175000, 79.970000)
ON CONFLICT (customer_id) DO UPDATE SET
  name = EXCLUDED.name,
  phone = EXCLUDED.phone,
  email = EXCLUDED.email,
  address = EXCLUDED.address;

-- -----------------------------------------------------------------------------
-- 4. Upsert Master Cooperative Workers (Shramik Verified)
-- -----------------------------------------------------------------------------
INSERT INTO worker_data (
  worker_id, name, phone, email, experience_years, hourly_rate, address, city,
  latitude, longitude, is_verified, is_active
) VALUES
  (1, 'Arvind Gupta', '9123456790', 'arvind.gupta@example.com', 9, 260.00, 'Civil Lines, Jabalpur', 'Jabalpur', 23.185000, 79.982000, TRUE, TRUE),
  (2, 'Ramesh Patel', '9123456782', 'ramesh.patel@example.com', 12, 350.00, 'Napier Town, Jabalpur', 'Jabalpur', 23.192000, 79.975000, TRUE, TRUE),
  (3, 'Suresh Raikwar', '9123456781', 'suresh.raikwar@example.com', 7, 300.00, 'Wright Town, Jabalpur', 'Jabalpur', 23.180000, 79.980000, TRUE, TRUE),
  (4, 'Mohan Vishwakarma', '9123456787', 'mohan.vishwakarma@example.com', 14, 320.00, 'Napier Town, Jabalpur', 'Jabalpur', 23.188000, 79.978000, TRUE, TRUE),
  (5, 'Imran Khan', '9123456784', 'imran.khan@example.com', 8, 380.00, 'Gorakhpur, Jabalpur', 'Jabalpur', 23.176000, 79.972000, TRUE, TRUE)
ON CONFLICT (worker_id) DO UPDATE SET
  name = EXCLUDED.name,
  phone = EXCLUDED.phone,
  email = EXCLUDED.email,
  experience_years = EXCLUDED.experience_years,
  hourly_rate = EXCLUDED.hourly_rate,
  is_verified = TRUE,
  is_active = TRUE;

-- Link Workers to Skills
INSERT INTO workers_skill (worker_id, skill_id, skill_level, experience_years) VALUES
  (1, 1, 'Expert', 9),
  (2, 3, 'Expert', 12),
  (3, 2, 'Expert', 7),
  (4, 4, 'Expert', 14),
  (5, 5, 'Expert', 8)
ON CONFLICT (worker_id, skill_id) DO UPDATE SET
  skill_level = EXCLUDED.skill_level,
  experience_years = EXCLUDED.experience_years;

-- -----------------------------------------------------------------------------
-- 5. Upsert Master Services
-- -----------------------------------------------------------------------------
INSERT INTO services (service_id, service_name, description, category, base_price, estimated_duration, skill_id) VALUES
  (1, 'Ceiling Fan Installation & Repair', 'Inspection, motor check, capacitor testing, and electrical repair.', 'ELECTRICAL', 250.00, 60, 1),
  (2, 'Lawn Mowing & Garden Care', 'Grass trimming, hedge pruning, weeding, and garden upkeep.', 'GARDENING', 350.00, 60, 3),
  (3, 'Kitchen Sink Leak & Pipe Repair', 'Leak detection, pipe sealing, tap spindle fitting, and drainage clearance.', 'PLUMBING', 300.00, 60, 2),
  (4, 'Wooden Door Hinge & Lock Alignment', 'Hinge replacement, mortise lock fitting, and wood planing.', 'CARPENTRY', 320.00, 60, 4),
  (5, 'Split AC Deep Cleaning & Inspection', 'Indoor/outdoor coil foam cleaning, gas check, and filter servicing.', 'HVAC', 380.00, 60, 5)
ON CONFLICT (service_id) DO UPDATE SET
  service_name = EXCLUDED.service_name,
  category = EXCLUDED.category,
  skill_id = EXCLUDED.skill_id;

-- -----------------------------------------------------------------------------
-- 6. Upsert & Reset the 5 Demo Booking Scenarios (#SH-0101 to #SH-0105 & #SH-0058)
-- -----------------------------------------------------------------------------
INSERT INTO bookings (
  booking_id, customer_id, worker_id, service_id, booking_date, start_time,
  address, description, estimated_price, amount, status, payment_status,
  start_otp, end_otp, start_otp_attempts, end_otp_attempts,
  is_start_otp_locked, is_end_otp_locked, worker_payout_amount, platform_tech_fee,
  welfare_pool_fee, total_amount, additional_service_charge, material_charge,
  final_amount, quotation_status, warranty_active
) VALUES
  -- Scenario 1: Electrical (#SH-0101)
  (101, 1, 1, 1, CURRENT_DATE, '10:00:00', 'Civil Lines, Jabalpur', 'Ceiling Fan Installation & Repair', 239.00, 239.00, 'ASSIGNED', 'UNPAID', '4821', '9134', 0, 0, FALSE, FALSE, 199.00, 30.00, 10.00, 239.00, 0.00, 0.00, 239.00, 'NONE', FALSE),
  -- Scenario 2: Gardening (#SH-0102)
  (102, 2, 2, 2, CURRENT_DATE, '10:00:00', 'Vijay Nagar, Jabalpur', 'Lawn Mowing & Garden Care', 239.00, 239.00, 'ASSIGNED', 'UNPAID', '4821', '9134', 0, 0, FALSE, FALSE, 199.00, 30.00, 10.00, 239.00, 0.00, 0.00, 239.00, 'NONE', FALSE),
  -- Scenario 3: Plumbing (#SH-0103)
  (103, 3, 3, 3, CURRENT_DATE, '10:00:00', 'Wright Town, Jabalpur', 'Kitchen Sink Leak & Pipe Repair', 239.00, 239.00, 'ASSIGNED', 'UNPAID', '4821', '9134', 0, 0, FALSE, FALSE, 199.00, 30.00, 10.00, 239.00, 0.00, 0.00, 239.00, 'NONE', FALSE),
  -- Scenario 4: Carpentry (#SH-0104)
  (104, 4, 4, 4, CURRENT_DATE, '10:00:00', 'Napier Town, Jabalpur', 'Wooden Door Hinge & Lock Alignment', 239.00, 239.00, 'ASSIGNED', 'UNPAID', '4821', '9134', 0, 0, FALSE, FALSE, 199.00, 30.00, 10.00, 239.00, 0.00, 0.00, 239.00, 'NONE', FALSE),
  -- Scenario 5: HVAC (#SH-0105)
  (105, 5, 5, 5, CURRENT_DATE, '10:00:00', 'Gorakhpur, Jabalpur', 'Split AC Deep Cleaning & Inspection', 239.00, 239.00, 'ASSIGNED', 'UNPAID', '4821', '9134', 0, 0, FALSE, FALSE, 199.00, 30.00, 10.00, 239.00, 0.00, 0.00, 239.00, 'NONE', FALSE),
  -- Companion Primary Live Demo Order (#SH-0058 / ID 58)
  (58, 1, 1, 1, CURRENT_DATE, '10:00:00', 'Civil Lines, Jabalpur', 'Ceiling Fan Installation & Repair', 239.00, 239.00, 'ASSIGNED', 'UNPAID', '4821', '9134', 0, 0, FALSE, FALSE, 199.00, 30.00, 10.00, 239.00, 0.00, 0.00, 239.00, 'NONE', FALSE)
ON CONFLICT (booking_id) DO UPDATE SET
  customer_id = EXCLUDED.customer_id,
  worker_id = EXCLUDED.worker_id,
  service_id = EXCLUDED.service_id,
  description = EXCLUDED.description,
  address = EXCLUDED.address,
  status = 'ASSIGNED',
  payment_status = 'UNPAID',
  start_otp = '4821',
  end_otp = '9134',
  start_otp_attempts = 0,
  end_otp_attempts = 0,
  is_start_otp_locked = FALSE,
  is_end_otp_locked = FALSE,
  start_otp_verified_at = NULL,
  end_otp_verified_at = NULL,
  last_otp_attempt_at = NULL,
  worker_payout_amount = 199.00,
  platform_tech_fee = 30.00,
  welfare_pool_fee = 10.00,
  total_amount = 239.00,
  additional_service_charge = 0.00,
  material_charge = 0.00,
  final_amount = 239.00,
  quotation_status = 'NONE',
  customer_approved_at = NULL,
  work_completed_at = NULL,
  payment_reference = NULL,
  payment_completed_at = NULL,
  settled_at = NULL,
  warranty_active = FALSE,
  warranty_started_at = NULL,
  warranty_expires_at = NULL;

-- Clean up any residual child quotations, payment records, and welfare ledger entries for demo IDs
DELETE FROM quotations WHERE booking_id IN (58, 101, 102, 103, 104, 105);
DELETE FROM payment_records WHERE booking_id IN (58, 101, 102, 103, 104, 105);
DELETE FROM cooperative_welfare_ledger WHERE booking_id IN (58, 101, 102, 103, 104, 105);

-- Ensure primary worker availability is reset to active
UPDATE availability SET is_available = TRUE WHERE worker_id IN (1, 2, 3, 4, 5);

COMMIT;
