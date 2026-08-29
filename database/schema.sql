-- =============================================================================
-- Cooperative Gig Services Platform for Household & Community Services
-- Database Schema (PostgreSQL) — SIH 2026 Problem Statement 26089
-- =============================================================================

-- Clean up any existing tables in reverse dependency order
DROP TABLE IF EXISTS ratings_reviews CASCADE;
DROP TABLE IF EXISTS bookings CASCADE;
DROP TABLE IF EXISTS services CASCADE;
DROP TABLE IF EXISTS availability CASCADE;
DROP TABLE IF EXISTS workers_skill CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
DROP TABLE IF EXISTS worker_data CASCADE;
DROP TABLE IF EXISTS customer_data CASCADE;

-- -----------------------------------------------------------------------------
-- 1. Table: customer_data
-- -----------------------------------------------------------------------------
CREATE TABLE customer_data (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    address VARCHAR(255),
    city VARCHAR(100) DEFAULT 'Jabalpur',
    latitude NUMERIC(9,6) DEFAULT 23.181500,
    longitude NUMERIC(9,6) DEFAULT 79.986400,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 2. Table: worker_data
-- -----------------------------------------------------------------------------
CREATE TABLE worker_data (
    worker_id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    experience_years INTEGER DEFAULT 0,
    address VARCHAR(255),
    city VARCHAR(100) DEFAULT 'Jabalpur',
    latitude NUMERIC(9,6) NOT NULL DEFAULT 23.181500,
    longitude NUMERIC(9,6) NOT NULL DEFAULT 79.986400,
    hourly_rate NUMERIC(10,2) DEFAULT 250.00,
    is_verified BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 3. Table: skills
-- -----------------------------------------------------------------------------
CREATE TABLE skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- -----------------------------------------------------------------------------
-- 4. Table: workers_skill
-- -----------------------------------------------------------------------------
CREATE TABLE workers_skill (
    worker_id INTEGER NOT NULL REFERENCES worker_data(worker_id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    skill_level VARCHAR(50) DEFAULT 'Intermediate',
    experience_years INTEGER DEFAULT 1,
    PRIMARY KEY (worker_id, skill_id)
);

-- -----------------------------------------------------------------------------
-- 5. Table: availability
-- -----------------------------------------------------------------------------
CREATE TABLE availability (
    availability_id SERIAL PRIMARY KEY,
    worker_id INTEGER NOT NULL REFERENCES worker_data(worker_id) ON DELETE CASCADE,
    date DATE DEFAULT CURRENT_DATE,
    start_time TIME,
    end_time TIME,
    is_available BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 6. Table: services
-- -----------------------------------------------------------------------------
CREATE TABLE services (
    service_id SERIAL PRIMARY KEY,
    service_name VARCHAR(150) NOT NULL,
    description TEXT,
    category VARCHAR(100) DEFAULT 'Household',
    base_price NUMERIC(10,2) NOT NULL DEFAULT 250.00,
    estimated_duration INTEGER DEFAULT 60,
    skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE RESTRICT
);

-- -----------------------------------------------------------------------------
-- 7. Table: bookings
-- -----------------------------------------------------------------------------
CREATE TABLE bookings (
    booking_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customer_data(customer_id) ON DELETE RESTRICT,
    worker_id INTEGER NOT NULL REFERENCES worker_data(worker_id) ON DELETE RESTRICT,
    service_id INTEGER NOT NULL REFERENCES services(service_id) ON DELETE RESTRICT,
    booking_date DATE DEFAULT CURRENT_DATE,
    start_time TIME,
    address VARCHAR(255),
    description TEXT,
    estimated_price NUMERIC(10,2),
    amount NUMERIC(10,2) NOT NULL DEFAULT 250.00,
    service_lat NUMERIC(9,6),
    service_lon NUMERIC(9,6),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    payment_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 8. Table: ratings_reviews
-- -----------------------------------------------------------------------------
CREATE TABLE ratings_reviews (
    review_id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(booking_id) ON DELETE CASCADE,
    customer_id INTEGER REFERENCES customer_data(customer_id) ON DELETE SET NULL,
    worker_id INTEGER REFERENCES worker_data(worker_id) ON DELETE SET NULL,
    rating NUMERIC(2,1) NOT NULL CHECK (rating >= 1.0 AND rating <= 5.0),
    review VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Indexes for Optimized Query Performance
-- -----------------------------------------------------------------------------
CREATE INDEX idx_customer_email ON customer_data(email);
CREATE INDEX idx_customer_phone ON customer_data(phone);
CREATE INDEX idx_worker_email ON worker_data(email);
CREATE INDEX idx_worker_phone ON worker_data(phone);
CREATE INDEX idx_worker_status ON worker_data(is_active, is_verified);
CREATE INDEX idx_workers_skill_skill ON workers_skill(skill_id);
CREATE INDEX idx_workers_skill_worker ON workers_skill(worker_id);
CREATE INDEX idx_availability_worker ON availability(worker_id, is_available);
CREATE INDEX idx_services_skill ON services(skill_id);
CREATE INDEX idx_services_category ON services(category);
CREATE INDEX idx_bookings_customer ON bookings(customer_id);
CREATE INDEX idx_bookings_worker ON bookings(worker_id);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_date_slot ON bookings(worker_id, booking_date, start_time);
CREATE INDEX idx_ratings_reviews_booking ON ratings_reviews(booking_id);
CREATE INDEX idx_ratings_reviews_worker ON ratings_reviews(worker_id);
