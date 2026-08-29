-- =============================================================================
-- Cooperative Gig Services Platform for Household & Community Services
-- Database Seed Data (PostgreSQL) — SIH 2026 Problem Statement 26089
-- =============================================================================

TRUNCATE TABLE ratings_reviews, bookings, services, availability, workers_skill, skills, worker_data, customer_data RESTART IDENTITY CASCADE;

-- -----------------------------------------------------------------------------
-- 1. Insert Skills (12 Categories)
-- -----------------------------------------------------------------------------
INSERT INTO skills (skill_name, description) VALUES
    ('Electrician', 'Electrical installation, wiring, switches, fan and appliance connections'),
    ('Plumber', 'Pipe fittings, leakage repair, sanitary fittings, drainage and taps'),
    ('Carpenter', 'Furniture making, wooden repairs, door fitting, locks and woodwork'),
    ('Painter', 'Interior & exterior wall painting, waterproofing, primer and touch-ups'),
    ('Appliance Repair', 'Troubleshooting washing machines, refrigerators, microwaves, and mixers'),
    ('House Cleaning', 'Deep home sanitation, kitchen scrubbing, bathroom cleaning, and mopping'),
    ('Gardener', 'Lawn mowing, hedge trimming, weeding, planting, and organic fertilizer care'),
    ('Pest Control', 'Eco-friendly pest eradication for cockroaches, termites, bed bugs, and rodents'),
    ('AC Technician', 'Air conditioner servicing, filter cleaning, gas refill, and installation'),
    ('Mason', 'Brickwork, tile laying, crack repair, plastering, and masonry renovation'),
    ('Security Guard', 'Premises surveillance, gate management, and event safety coordination'),
    ('Babysitter', 'Childcare, elder assistance, and household caregiving services');

-- -----------------------------------------------------------------------------
-- 2. Insert Services (12 Offerings)
-- -----------------------------------------------------------------------------
INSERT INTO services (service_name, description, category, base_price, estimated_duration, skill_id) VALUES
    ('Ceiling Fan Installation & Repair', 'Prompt repair of fans, switches, and household wiring.', 'Electrical', 250.00, 45, (SELECT skill_id FROM skills WHERE skill_name = 'Electrician')),
    ('Switchboard & MCB Repair', 'Diagnosis and repair of short circuits and circuit breakers.', 'Electrical', 300.00, 60, (SELECT skill_id FROM skills WHERE skill_name = 'Electrician')),
    ('Pipe Leakage & Drainage Fix', 'Fix leaking taps, pipes, and cleared clogged drainage lines.', 'Plumbing', 350.00, 60, (SELECT skill_id FROM skills WHERE skill_name = 'Plumber')),
    ('Bathroom Sanitary Fitting', 'Install or replace washbasins, faucets, showers, and cisterns.', 'Plumbing', 500.00, 90, (SELECT skill_id FROM skills WHERE skill_name = 'Plumber')),
    ('Furniture Assembly & Repair', 'Woodwork repair, hinge adjustment, and flat-pack furniture setup.', 'Carpentry', 450.00, 90, (SELECT skill_id FROM skills WHERE skill_name = 'Carpenter')),
    ('Interior Room Wall Painting', 'High-quality room painting with double-coat primer and finish.', 'Painting', 850.00, 180, (SELECT skill_id FROM skills WHERE skill_name = 'Painter')),
    ('Washing Machine Repair', 'Motor diagnostics, drum alignment, and water intake repairs.', 'Appliance', 500.00, 75, (SELECT skill_id FROM skills WHERE skill_name = 'Appliance Repair')),
    ('Full House Deep Cleaning', 'Comprehensive floor scrubbing, bathroom descaling, and sanitation.', 'Cleaning', 1200.00, 240, (SELECT skill_id FROM skills WHERE skill_name = 'House Cleaning')),
    ('Lawn Mowing & Garden Care', 'Grass trimming, hedge pruning, weeding, and garden upkeep.', 'Gardening', 350.00, 60, (SELECT skill_id FROM skills WHERE skill_name = 'Gardener')),
    ('General Pest & Cockroach Control', 'Odorless gel pest treatment for roaches, ants, and spiders.', 'Pest Control', 750.00, 90, (SELECT skill_id FROM skills WHERE skill_name = 'Pest Control')),
    ('AC Servicing & Gas Refill', 'Coil cleaning, filter washing, refrigerant top-up, and cooling check.', 'AC & Cooling', 650.00, 60, (SELECT skill_id FROM skills WHERE skill_name = 'AC Technician')),
    ('Tile & Brick Crack Repair', 'Tile grouting, floor plastering, and wall patch renovation.', 'Masonry', 600.00, 120, (SELECT skill_id FROM skills WHERE skill_name = 'Mason'));

-- -----------------------------------------------------------------------------
-- 3. Insert Customers (Password: Password123!)
-- Hash: $2b$12$4mU3Z.4zBf95eS7/QxRjQ.3vW7j3hLqC9Kx3Z1Y7vW7j3hLqC9Kx3 (or bcrypt)
-- -----------------------------------------------------------------------------
INSERT INTO customer_data (name, phone, email, password_hash, address, city, latitude, longitude) VALUES
    ('Demo Customer', '9876543200', 'customer@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Civil Lines, Jabalpur', 'Jabalpur', 23.181500, 79.986400),
    ('Rahul Verma', '9876543210', 'rahul.verma@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Wright Town, Jabalpur', 'Jabalpur', 23.182000, 79.985000),
    ('Ananya Sharma', '9876543211', 'ananya.sharma@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Napier Town, Jabalpur', 'Jabalpur', 23.178000, 79.981000),
    ('Priya Patel', '9876543212', 'priya.patel@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Vijay Nagar, Jabalpur', 'Jabalpur', 23.195000, 79.970000),
    ('Amit Singh', '9876543213', 'amit.singh@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Madan Mahal, Jabalpur', 'Jabalpur', 23.165000, 79.960000),
    ('Vikram Joshi', '9876543214', 'vikram.joshi@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Gorakhpur, Jabalpur', 'Jabalpur', 23.160000, 79.990000),
    ('Sunita Rao', '9876543215', 'sunita.rao@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Adhartal, Jabalpur', 'Jabalpur', 23.210000, 79.965000),
    ('Deepak Gupta', '9876543216', 'deepak.gupta@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Sadar Bazar, Jabalpur', 'Jabalpur', 23.170000, 79.995000),
    ('Neha Tiwari', '9876543217', 'neha.tiwari@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Ganjipura, Jabalpur', 'Jabalpur', 23.184000, 79.975000),
    ('Rohit Mehta', '9876543218', 'rohit.mehta@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 'Ranjhi, Jabalpur', 'Jabalpur', 23.205000, 80.010000);

-- -----------------------------------------------------------------------------
-- 4. Insert Workers
-- -----------------------------------------------------------------------------
INSERT INTO worker_data (name, phone, email, password_hash, experience_years, hourly_rate, address, city, latitude, longitude, is_verified, is_active) VALUES
    ('Demo Worker', '9123456700', 'worker@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 8, 250.00, 'Civil Lines, Jabalpur', 'Jabalpur', 23.185000, 79.982000, TRUE, TRUE),
    ('Suresh Kumar', '9123456781', 'suresh.kumar@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 5, 300.00, 'Wright Town, Jabalpur', 'Jabalpur', 23.176000, 79.991000, TRUE, TRUE),
    ('Ramesh Patel', '9123456782', 'ramesh.patel@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 12, 400.00, 'Napier Town, Jabalpur', 'Jabalpur', 23.192000, 79.975000, TRUE, TRUE),
    ('Dinesh Yadav', '9123456783', 'dinesh.yadav@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 3, 200.00, 'Vijay Nagar, Jabalpur', 'Jabalpur', 23.165000, 80.002000, FALSE, TRUE),
    ('Manoj Tiwari', '9123456784', 'manoj.tiwari@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 6, 350.00, 'Madan Mahal, Jabalpur', 'Jabalpur', 23.201000, 79.968000, TRUE, TRUE),
    ('Anita Devi', '9123456785', 'anita.devi@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 4, 250.00, 'Gorakhpur, Jabalpur', 'Jabalpur', 23.153000, 80.015000, TRUE, TRUE),
    ('Ramu Lal', '9123456786', 'ramu.lal@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 10, 220.00, 'Adhartal, Jabalpur', 'Jabalpur', 23.215000, 79.950000, TRUE, TRUE),
    ('Vijay Verma', '9123456787', 'vijay.verma@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 2, 280.00, 'Sadar Bazar, Jabalpur', 'Jabalpur', 23.138000, 80.028000, FALSE, TRUE),
    ('Santosh Mishra', '9123456788', 'santosh.mishra@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 7, 320.00, 'Ganjipura, Jabalpur', 'Jabalpur', 23.230000, 79.932000, TRUE, TRUE),
    ('Jagdish Prasad', '9123456789', 'jagdish.prasad@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 15, 380.00, 'Ranjhi, Jabalpur', 'Jabalpur', 23.120000, 80.045000, TRUE, TRUE),
    ('Arvind Gupta', '9123456790', 'arvind.gupta@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 9, 260.00, 'Civil Lines, Jabalpur', 'Jabalpur', 23.182000, 79.986000, TRUE, TRUE),
    ('Vikas Chourasia', '9123456791', 'vikas.c@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 1, 180.00, 'Napier Town, Jabalpur', 'Jabalpur', 23.187000, 79.989000, TRUE, TRUE),
    ('Sanjay Soni', '9123456792', 'sanjay.soni@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 4, 300.00, 'Wright Town, Jabalpur', 'Jabalpur', 23.172000, 79.978000, TRUE, FALSE),
    ('Pappu Lodhi', '9123456793', 'pappu.lodhi@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 6, 220.00, 'Madan Mahal, Jabalpur', 'Jabalpur', 23.198000, 79.995000, FALSE, FALSE),
    ('Kamlesh Sen', '9123456794', 'kamlesh.sen@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 5, 290.00, 'Vijay Nagar, Jabalpur', 'Jabalpur', 23.160000, 79.965000, TRUE, TRUE),
    ('Sunita Bai', '9123456795', 'sunita.bai@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 8, 300.00, 'Adhartal, Jabalpur', 'Jabalpur', 23.208000, 80.010000, TRUE, TRUE),
    ('Mohan Sahu', '9123456796', 'mohan.sahu@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 2, 200.00, 'Gorakhpur, Jabalpur', 'Jabalpur', 23.145000, 79.955000, TRUE, TRUE),
    ('Anil Vishwakarma', '9123456797', 'anil.v@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 11, 450.00, 'Sadar Bazar, Jabalpur', 'Jabalpur', 23.225000, 80.025000, TRUE, TRUE),
    ('Rakesh Dubey', '9123456798', 'rakesh.dubey@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 3, 270.00, 'Ganjipura, Jabalpur', 'Jabalpur', 23.130000, 79.940000, TRUE, TRUE),
    ('Pradeep Sen', '9123456799', 'pradeep.sen@example.com', '$2b$12$Q7gYm29kH7l80BvhxHkWyei8qH8wV73R9Q.Z54H3vW7j3hLqC9Kx3', 7, 340.00, 'Ranjhi, Jabalpur', 'Jabalpur', 23.245000, 80.050000, TRUE, TRUE);

-- -----------------------------------------------------------------------------
-- 5. Insert Worker-Skill Mappings
-- -----------------------------------------------------------------------------
INSERT INTO workers_skill (worker_id, skill_id, skill_level, experience_years) VALUES
    (1, 1, 'Expert', 8),
    (1, 9, 'Expert', 6),
    (2, 2, 'Intermediate', 5),
    (3, 3, 'Expert', 12),
    (3, 10, 'Expert', 10),
    (4, 4, 'Intermediate', 3),
    (5, 5, 'Expert', 6),
    (5, 1, 'Intermediate', 4),
    (6, 6, 'Expert', 4),
    (7, 7, 'Expert', 10),
    (8, 8, 'Beginner', 2),
    (9, 9, 'Expert', 7),
    (9, 1, 'Intermediate', 5),
    (10, 10, 'Expert', 15),
    (10, 2, 'Expert', 12),
    (11, 1, 'Expert', 9),
    (12, 2, 'Beginner', 1),
    (13, 3, 'Intermediate', 4),
    (14, 4, 'Intermediate', 6),
    (15, 5, 'Intermediate', 5),
    (16, 6, 'Expert', 8),
    (16, 8, 'Intermediate', 5),
    (17, 7, 'Beginner', 2),
    (18, 3, 'Expert', 11),
    (18, 10, 'Expert', 8),
    (19, 9, 'Intermediate', 3),
    (20, 8, 'Expert', 7);

-- -----------------------------------------------------------------------------
-- 6. Insert Availability
-- -----------------------------------------------------------------------------
INSERT INTO availability (worker_id, date, start_time, end_time, is_available)
SELECT worker_id, CURRENT_DATE, '09:00:00', '18:00:00', is_active FROM worker_data;

-- -----------------------------------------------------------------------------
-- 7. Insert Bookings
-- -----------------------------------------------------------------------------
INSERT INTO bookings (customer_id, worker_id, service_id, booking_date, start_time, address, description, amount, estimated_price, service_lat, service_lon, status, payment_status) VALUES
    (1, 1, 1, CURRENT_DATE - INTERVAL '10 days', '10:00:00', 'Civil Lines, Jabalpur', 'Ceiling fan repair', 250.00, 250.00, 23.181500, 79.986400, 'COMPLETED', 'PAID'),
    (2, 1, 1, CURRENT_DATE - INTERVAL '8 days', '14:00:00', 'Wright Town, Jabalpur', 'Fan noise troubleshooting', 250.00, 250.00, 23.182000, 79.985000, 'COMPLETED', 'PAID'),
    (3, 2, 3, CURRENT_DATE - INTERVAL '7 days', '11:00:00', 'Napier Town, Jabalpur', 'Bathroom drain pipe fix', 350.00, 350.00, 23.178000, 79.981000, 'COMPLETED', 'PAID'),
    (4, 3, 5, CURRENT_DATE - INTERVAL '6 days', '09:30:00', 'Vijay Nagar, Jabalpur', 'Wooden wardrobe assembly', 450.00, 450.00, 23.195000, 79.970000, 'COMPLETED', 'PAID'),
    (5, 5, 7, CURRENT_DATE - INTERVAL '5 days', '15:00:00', 'Madan Mahal, Jabalpur', 'Washing machine motor service', 500.00, 500.00, 23.165000, 79.960000, 'COMPLETED', 'PAID'),
    (6, 6, 8, CURRENT_DATE - INTERVAL '5 days', '10:00:00', 'Gorakhpur, Jabalpur', 'Deep home cleaning', 1200.00, 1200.00, 23.160000, 79.990000, 'COMPLETED', 'PAID'),
    (7, 9, 11, CURRENT_DATE - INTERVAL '4 days', '13:00:00', 'Ganjipura, Jabalpur', 'AC gas refill', 650.00, 650.00, 23.184000, 79.975000, 'COMPLETED', 'PAID'),
    (8, 10, 12, CURRENT_DATE - INTERVAL '3 days', '11:00:00', 'Ranjhi, Jabalpur', 'Tile crack plastering', 600.00, 600.00, 23.205000, 80.010000, 'COMPLETED', 'PAID'),
    (9, 11, 1, CURRENT_DATE - INTERVAL '3 days', '16:00:00', 'Civil Lines, Jabalpur', 'Switchboard rewiring', 250.00, 250.00, 23.182000, 79.986000, 'COMPLETED', 'PAID'),
    (10, 11, 2, CURRENT_DATE - INTERVAL '2 days', '10:30:00', 'Napier Town, Jabalpur', 'MCB repair', 300.00, 300.00, 23.178000, 79.981000, 'COMPLETED', 'PAID'),
    (1, 12, 3, CURRENT_DATE - INTERVAL '2 days', '12:00:00', 'Civil Lines, Jabalpur', 'Tap washer replacement', 350.00, 350.00, 23.181500, 79.986400, 'COMPLETED', 'PAID'),
    (2, 16, 8, CURRENT_DATE - INTERVAL '1 day', '09:00:00', 'Wright Town, Jabalpur', 'Kitchen deep scrubbing', 1200.00, 1200.00, 23.182000, 79.985000, 'COMPLETED', 'PAID'),
    (3, 18, 5, CURRENT_DATE - INTERVAL '1 day', '14:00:00', 'Napier Town, Jabalpur', 'Door lock and hinge fix', 450.00, 450.00, 23.178000, 79.981000, 'COMPLETED', 'PAID'),
    (4, 11, 1, CURRENT_DATE, '11:00:00', 'Vijay Nagar, Jabalpur', 'Active electrician request', 250.00, 250.00, 23.195000, 79.970000, 'ACCEPTED', 'PENDING'),
    (5, 7, 9, CURRENT_DATE, '15:00:00', 'Madan Mahal, Jabalpur', 'Garden weeding', 350.00, 350.00, 23.165000, 79.960000, 'PENDING', 'PENDING'),
    (7, 4, 6, CURRENT_DATE - INTERVAL '12 days', '10:00:00', 'Adhartal, Jabalpur', 'Cancelled wall paint job', 850.00, 850.00, 23.210000, 79.965000, 'CANCELLED', 'REFUNDED');

-- -----------------------------------------------------------------------------
-- 8. Insert Ratings and Reviews (1-to-1 Constraint)
-- -----------------------------------------------------------------------------
INSERT INTO ratings_reviews (booking_id, customer_id, worker_id, rating, review) VALUES
    (1, 1, 1, 5.0, 'Outstanding electrician! Solved the short-circuit issue and installed the ceiling fan flawlessly.'),
    (2, 2, 1, 4.5, 'Very polite and arrived right on time. Clean work.'),
    (3, 3, 2, 4.0, 'Fixed the pipeline leakage and cleared the bathroom drain properly.'),
    (4, 4, 3, 5.0, 'Master craftsman. Assembled my large wooden wardrobe with great precision.'),
    (5, 5, 5, 4.5, 'Diagnosed the washing machine noise quickly and replaced the worn belt.'),
    (6, 6, 6, 5.0, 'Entire house is sparkling clean. Sanitized kitchen and bathrooms thoroughly.'),
    (7, 7, 9, 4.5, 'AC cooling was restored completely after gas refill and pressure wash.'),
    (8, 8, 10, 4.0, 'Good masonry repair on wall cracks and neat tile fitting.'),
    (9, 9, 11, 5.0, 'Arvind is fantastic! Repaired our switchboard in under 20 minutes.'),
    (10, 10, 11, 4.8, 'Neat electrical work, tested all switches before leaving.'),
    (11, 1, 12, 3.5, 'Fixed the tap leak, arrived 15 mins late but did the job.'),
    (12, 2, 16, 5.0, 'Very reliable deep home cleaning team.'),
    (13, 3, 18, 5.0, 'Expert carpentry work on door frame.');
