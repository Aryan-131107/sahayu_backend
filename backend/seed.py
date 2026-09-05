"""
seed.py — Non-Destructive, Idempotent Database Seeder for Sahāyu Platform
Supports local PostgreSQL and remote Supabase PostgreSQL.

Features:
- Does NOT drop existing tables or delete existing production data.
- Inserts seed data in strict foreign-key dependency order.
- Checks for existing records before inserting (avoids duplicates / 409 conflicts).
- Clear progress logging and error reporting.
"""

import sys
from datetime import date, timedelta, time
from sqlalchemy import text, func
from app.database import engine, SessionLocal, Base
from app.models import (
    CustomerData, WorkerData, AdminUser, Skill, WorkerSkill, Availability, Service, Booking, RatingReview,
    CooperativeWelfareLedger
)
from app.core.security import get_password_hash


def seed_database():
    """Idempotently seed admin, skills, services, customers, workers, bookings, and reviews."""
    print("=" * 60)
    print("  Sahayu Database Seeder (PostgreSQL / Supabase)")
    print("=" * 60)
    
    # Ensure tables exist without dropping existing schema
    try:
        Base.metadata.create_all(bind=engine)
        print("[OK] Verified database tables exist.")
    except Exception as e:
        print(f"[WARNING] Table verification warning: {e}")

    db = SessionLocal()
    try:
        hashed_pwd = get_password_hash("Password123!")

        # ─────────────────────────────────────────────────────
        # 0. SEED ADMIN USER (1 Account)
        # ─────────────────────────────────────────────────────
        print("[*] Checking & Seeding Admin User...")
        admin_email = "admin@example.com"
        existing_admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == admin_email.lower()).first()
        if not existing_admin:
            admin_user = AdminUser(
                name="System Administrator",
                email=admin_email,
                password_hash=hashed_pwd,
                role="admin",
            )
            db.add(admin_user)
            db.commit()
            print("[OK] Demo Admin ready: admin@example.com (1 newly added).")
        else:
            existing_admin.password_hash = hashed_pwd
            db.commit()
            print("[OK] Demo Admin ready: admin@example.com (password hash refreshed).")

        # ─────────────────────────────────────────────────────
        # 1. SEED SKILLS (12 Categories)
        # ─────────────────────────────────────────────────────
        print("[*] Checking & Seeding Skills...")
        skills_data = [
            ("Electrician", "Electrical installation, wiring, switches, fan and appliance connections"),
            ("Plumber", "Pipe fittings, leakage repair, sanitary fittings, drainage and taps"),
            ("Carpenter", "Furniture making, wooden repairs, door fitting, locks and woodwork"),
            ("Painter", "Interior & exterior wall painting, waterproofing, primer and touch-ups"),
            ("Appliance Repair", "Troubleshooting washing machines, refrigerators, microwaves, and mixers"),
            ("House Cleaning", "Deep home sanitation, kitchen scrubbing, bathroom cleaning, and mopping"),
            ("Gardener", "Lawn mowing, hedge trimming, weeding, planting, and organic fertilizer care"),
            ("Pest Control", "Eco-friendly pest eradication for cockroaches, termites, bed bugs, and rodents"),
            ("AC Technician", "Air conditioner servicing, filter cleaning, gas refill, and installation"),
            ("Mason", "Brickwork, tile laying, crack repair, plastering, and masonry renovation"),
            ("Security Guard", "Premises surveillance, gate management, and event safety coordination"),
            ("Babysitter", "Childcare, elder assistance, and household caregiving services"),
        ]

        skill_objs = {}
        skills_added = 0
        for name, desc in skills_data:
            existing = db.query(Skill).filter(func.lower(Skill.skill_name) == name.lower()).first()
            if not existing:
                s = Skill(skill_name=name, description=desc)
                db.add(s)
                db.flush()
                skill_objs[name] = s
                skills_added += 1
            else:
                skill_objs[name] = existing

        db.commit()
        print(f"[OK] Skills ready: {len(skill_objs)} total ({skills_added} newly added).")

        # ─────────────────────────────────────────────────────
        # 2. SEED SERVICES (12 Offerings)
        # ─────────────────────────────────────────────────────
        print("[*] Checking & Seeding Services...")
        services_data = [
            ("Ceiling Fan Installation & Repair", "Prompt repair of fans, switches, and household wiring.", "Electrical", 250.00, 45, "Electrician"),
            ("Switchboard & MCB Repair", "Diagnosis and repair of short circuits and circuit breakers.", "Electrical", 300.00, 60, "Electrician"),
            ("Pipe Leakage & Drainage Fix", "Fix leaking taps, pipes, and cleared clogged drainage lines.", "Plumbing", 350.00, 60, "Plumber"),
            ("Bathroom Sanitary Fitting", "Install or replace washbasins, faucets, showers, and cisterns.", "Plumbing", 500.00, 90, "Plumber"),
            ("Furniture Assembly & Repair", "Woodwork repair, hinge adjustment, and flat-pack furniture setup.", "Carpentry", 450.00, 90, "Carpenter"),
            ("Interior Room Wall Painting", "High-quality room painting with double-coat primer and finish.", "Painting", 850.00, 180, "Painter"),
            ("Washing Machine Repair", "Motor diagnostics, drum alignment, and water intake repairs.", "Appliance", 500.00, 75, "Appliance Repair"),
            ("Full House Deep Cleaning", "Comprehensive floor scrubbing, bathroom descaling, and sanitation.", "Cleaning", 1200.00, 240, "House Cleaning"),
            ("Lawn Mowing & Garden Care", "Grass trimming, hedge pruning, weeding, and garden upkeep.", "Gardening", 350.00, 60, "Gardener"),
            ("General Pest & Cockroach Control", "Odorless gel pest treatment for roaches, ants, and spiders.", "Pest Control", 750.00, 90, "Pest Control"),
            ("AC Servicing & Gas Refill", "Coil cleaning, filter washing, refrigerant top-up, and cooling check.", "AC & Cooling", 650.00, 60, "AC Technician"),
            ("Tile & Brick Crack Repair", "Tile grouting, floor plastering, and wall patch renovation.", "Masonry", 600.00, 120, "Mason"),
        ]

        services_added = 0
        service_map = {}
        for s_name, desc, cat, price, dur, sk_name in services_data:
            existing = db.query(Service).filter(func.lower(Service.service_name) == s_name.lower()).first()
            if not existing and sk_name in skill_objs:
                svc = Service(
                    service_name=s_name,
                    description=desc,
                    category=cat,
                    base_price=price,
                    estimated_duration=dur,
                    is_active=True,
                    skill_id=skill_objs[sk_name].skill_id,
                )
                db.add(svc)
                db.flush()
                service_map[s_name] = svc
                services_added += 1
            elif existing:
                service_map[s_name] = existing

        db.commit()
        print(f"[OK] Services ready: {len(service_map)} total ({services_added} newly added).")

        # ─────────────────────────────────────────────────────
        # 3. SEED CUSTOMERS (10 Accounts)
        # ─────────────────────────────────────────────────────
        print("[*] Checking & Seeding Customers...")

        customers_data = [
            ("Demo Customer", "9876543200", "customer@example.com", "Civil Lines, Jabalpur", "Jabalpur", 23.181500, 79.986400),
            ("Rahul Verma", "9876543210", "rahul.verma@example.com", "Wright Town, Jabalpur", "Jabalpur", 23.182000, 79.985000),
            ("Ananya Sharma", "9876543211", "ananya.sharma@example.com", "Napier Town, Jabalpur", "Jabalpur", 23.178000, 79.981000),
            ("Priya Patel", "9876543212", "priya.patel@example.com", "Vijay Nagar, Jabalpur", "Jabalpur", 23.195000, 79.970000),
            ("Amit Singh", "9876543213", "amit.singh@example.com", "Madan Mahal, Jabalpur", "Jabalpur", 23.165000, 79.960000),
            ("Vikram Joshi", "9876543214", "vikram.joshi@example.com", "Gorakhpur, Jabalpur", "Jabalpur", 23.160000, 79.990000),
            ("Sunita Rao", "9876543215", "sunita.rao@example.com", "Adhartal, Jabalpur", "Jabalpur", 23.210000, 79.965000),
            ("Deepak Gupta", "9876543216", "deepak.gupta@example.com", "Sadar Bazar, Jabalpur", "Jabalpur", 23.170000, 79.995000),
            ("Neha Tiwari", "9876543217", "neha.tiwari@example.com", "Ganjipura, Jabalpur", "Jabalpur", 23.184000, 79.975000),
            ("Rohit Mehta", "9876543218", "rohit.mehta@example.com", "Ranjhi, Jabalpur", "Jabalpur", 23.205000, 80.010000),
        ]

        cust_objs = []
        cust_added = 0
        cust_pwd_fixed = 0
        for name, phone, email, addr, city, lat, lon in customers_data:
            existing = db.query(CustomerData).filter(
                (func.lower(CustomerData.email) == email.lower()) | (CustomerData.phone == phone)
            ).first()
            if not existing:
                c = CustomerData(
                    name=name,
                    phone=phone,
                    email=email.lower(),
                    password_hash=hashed_pwd,
                    address=addr,
                    city=city,
                    latitude=lat,
                    longitude=lon,
                )
                db.add(c)
                db.flush()
                cust_objs.append(c)
                cust_added += 1
            else:
                existing.password_hash = hashed_pwd
                cust_pwd_fixed += 1
                cust_objs.append(existing)

        db.commit()
        print(f"[OK] Customers ready: {len(cust_objs)} total ({cust_added} newly added, {cust_pwd_fixed} password hashes refreshed).")


        # ─────────────────────────────────────────────────────
        # 4. SEED WORKERS & SKILLS (20 Accounts with Demo Shramik Verification)
        # ─────────────────────────────────────────────────────
        print("[*] Checking & Seeding Workers...")
        workers_data = [
            ("Demo Worker", "9123456700", "worker@example.com", 8, 250.00, "Civil Lines, Jabalpur", "Jabalpur", 23.185000, 79.982000, True, True, "SHR-MP-2026-1001", "CERT-ITI-ELEC-2023", "VERIFIED", "BOTH", [("Electrician", "Expert", 8), ("AC Technician", "Expert", 6)]),
            ("Suresh Kumar", "9123456781", "suresh.kumar@example.com", 5, 300.00, "Wright Town, Jabalpur", "Jabalpur", 23.176000, 79.991000, True, True, "SHR-MP-2026-1002", None, "VERIFIED", "DEMO_SHRAMIK", [("Plumber", "Intermediate", 5)]),
            ("Ramesh Patel", "9123456782", "ramesh.patel@example.com", 12, 400.00, "Napier Town, Jabalpur", "Jabalpur", 23.192000, 79.975000, True, True, "SHR-MP-2026-1003", None, "VERIFIED", "DEMO_SHRAMIK", [("Carpenter", "Expert", 12), ("Mason", "Expert", 10)]),
            ("Dinesh Yadav", "9123456783", "dinesh.yadav@example.com", 3, 200.00, "Vijay Nagar, Jabalpur", "Jabalpur", 23.165000, 80.002000, False, True, "SHR-MP-2026-1004", None, "PENDING", "DEMO_SHRAMIK", [("Painter", "Intermediate", 3)]),
            ("Manoj Tiwari", "9123456784", "manoj.tiwari@example.com", 6, 350.00, "Madan Mahal, Jabalpur", "Jabalpur", 23.201000, 79.968000, False, True, "SHR-MP-2026-1005", "CERT-APPL-2022", "REJECTED", "SKILL_CERTIFICATE", [("Appliance Repair", "Expert", 6), ("Electrician", "Intermediate", 4)]),
            ("Anita Devi", "9123456785", "anita.devi@example.com", 4, 250.00, "Gorakhpur, Jabalpur", "Jabalpur", 23.153000, 80.015000, True, True, "SHR-MP-2026-1006", None, "VERIFIED", "DEMO_SHRAMIK", [("House Cleaning", "Expert", 4)]),
            ("Ramu Lal", "9123456786", "ramu.lal@example.com", 10, 220.00, "Adhartal, Jabalpur", "Jabalpur", 23.215000, 79.950000, True, True, "SHR-MP-2026-1007", None, "VERIFIED", "DEMO_SHRAMIK", [("Gardener", "Expert", 10)]),
            ("Vijay Verma", "9123456787", "vijay.verma@example.com", 2, 280.00, "Sadar Bazar, Jabalpur", "Jabalpur", 23.138000, 80.028000, False, True, "SHR-MP-2026-1008", None, "PENDING", "DEMO_SHRAMIK", [("Pest Control", "Beginner", 2)]),
            ("Santosh Mishra", "9123456788", "santosh.mishra@example.com", 7, 320.00, "Ganjipura, Jabalpur", "Jabalpur", 23.230000, 79.932000, True, True, "SHR-MP-2026-1009", None, "VERIFIED", "DEMO_SHRAMIK", [("AC Technician", "Expert", 7), ("Electrician", "Intermediate", 5)]),
            ("Jagdish Prasad", "9123456789", "jagdish.prasad@example.com", 15, 380.00, "Ranjhi, Jabalpur", "Jabalpur", 23.120000, 80.045000, True, True, "SHR-MP-2026-1010", None, "VERIFIED", "DEMO_SHRAMIK", [("Mason", "Expert", 15), ("Plumber", "Expert", 12)]),
            ("Arvind Gupta", "9123456790", "arvind.gupta@example.com", 9, 260.00, "Civil Lines, Jabalpur", "Jabalpur", 23.182000, 79.986000, True, True, "SHR-MP-2026-1011", None, "VERIFIED", "DEMO_SHRAMIK", [("Electrician", "Expert", 9)]),
            ("Vikas Chourasia", "9123456791", "vikas.c@example.com", 1, 180.00, "Napier Town, Jabalpur", "Jabalpur", 23.187000, 79.989000, True, True, "SHR-MP-2026-1012", None, "VERIFIED", "DEMO_SHRAMIK", [("Plumber", "Beginner", 1)]),
            ("Sanjay Soni", "9123456792", "sanjay.soni@example.com", 4, 300.00, "Wright Town, Jabalpur", "Jabalpur", 23.172000, 79.978000, True, False, "SHR-MP-2026-1013", None, "VERIFIED", "DEMO_SHRAMIK", [("Carpenter", "Intermediate", 4)]),
            ("Pappu Lodhi", "9123456793", "pappu.lodhi@example.com", 6, 220.00, "Madan Mahal, Jabalpur", "Jabalpur", 23.198000, 79.995000, False, False, "SHR-MP-2026-1014", None, "PENDING", "DEMO_SHRAMIK", [("Painter", "Intermediate", 6)]),
            ("Kamlesh Sen", "9123456794", "kamlesh.sen@example.com", 5, 290.00, "Vijay Nagar, Jabalpur", "Jabalpur", 23.160000, 79.965000, True, True, "SHR-MP-2026-1015", None, "VERIFIED", "DEMO_SHRAMIK", [("Appliance Repair", "Intermediate", 5)]),
            ("Sunita Bai", "9123456795", "sunita.bai@example.com", 8, 300.00, "Adhartal, Jabalpur", "Jabalpur", 23.208000, 80.010000, True, True, "SHR-MP-2026-1016", None, "VERIFIED", "DEMO_SHRAMIK", [("House Cleaning", "Expert", 8), ("Pest Control", "Intermediate", 5)]),
            ("Mohan Sahu", "9123456796", "mohan.sahu@example.com", 2, 200.00, "Gorakhpur, Jabalpur", "Jabalpur", 23.145000, 79.955000, True, True, "SHR-MP-2026-1017", None, "VERIFIED", "DEMO_SHRAMIK", [("Gardener", "Beginner", 2)]),
            ("Anil Vishwakarma", "9123456797", "anil.v@example.com", 11, 450.00, "Sadar Bazar, Jabalpur", "Jabalpur", 23.225000, 80.025000, True, True, "SHR-MP-2026-1018", None, "VERIFIED", "DEMO_SHRAMIK", [("Carpenter", "Expert", 11), ("Mason", "Expert", 8)]),
            ("Rakesh Dubey", "9123456798", "rakesh.dubey@example.com", 3, 270.00, "Ganjipura, Jabalpur", "Jabalpur", 23.130000, 79.940000, True, True, "SHR-MP-2026-1019", None, "VERIFIED", "DEMO_SHRAMIK", [("AC Technician", "Intermediate", 3)]),
            ("Pradeep Sen", "9123456799", "pradeep.sen@example.com", 7, 340.00, "Ranjhi, Jabalpur", "Jabalpur", 23.245000, 80.050000, True, True, "SHR-MP-2026-1020", None, "VERIFIED", "DEMO_SHRAMIK", [("Pest Control", "Expert", 7)]),
        ]

        worker_objs = []
        workers_added = 0
        workers_pwd_fixed = 0
        for name, phone, email, exp, rate, addr, city, lat, lon, verified, active, shramik, cert, v_status, v_type, skills_list in workers_data:
            existing = db.query(WorkerData).filter(
                (func.lower(WorkerData.email) == email.lower()) | (WorkerData.phone == phone)
            ).first()
            if not existing:
                w = WorkerData(
                    name=name,
                    phone=phone,
                    email=email.lower(),
                    password_hash=hashed_pwd,
                    experience_years=exp,
                    hourly_rate=rate,
                    address=addr,
                    city=city,
                    latitude=lat,
                    longitude=lon,
                    is_verified=verified,
                    is_active=active,
                    shramik_id=shramik,
                    skill_certificate=cert,
                    verification_status=v_status,
                    verification_type=v_type,
                    verified_at=func.now() if verified else None,
                )
                db.add(w)
                db.flush()
                worker_objs.append(w)
                workers_added += 1

                for s_name, level, s_exp in skills_list:
                    sk = skill_objs.get(s_name)
                    if sk:
                        ws = WorkerSkill(
                            worker_id=w.worker_id,
                            skill_id=sk.skill_id,
                            skill_level=level,
                            experience_years=s_exp,
                        )
                        db.add(ws)

                avail = Availability(
                    worker_id=w.worker_id,
                    date=date.today(),
                    start_time=time(9, 0),
                    end_time=time(18, 0),
                    is_available=active,
                )
                db.add(avail)
            else:
                existing.password_hash = hashed_pwd
                existing.shramik_id = shramik
                existing.skill_certificate = cert
                existing.verification_status = v_status
                existing.verification_type = v_type
                existing.is_verified = verified
                existing.verified_at = func.now() if verified else None
                workers_pwd_fixed += 1
                worker_objs.append(existing)

        db.commit()
        print(f"[OK] Workers ready: {len(worker_objs)} total ({workers_added} newly added, {workers_pwd_fixed} verification & password records refreshed).")


        # ─────────────────────────────────────────────────────
        # 5. SEED BOOKINGS & REVIEWS
        # ─────────────────────────────────────────────────────
        print("[*] Checking & Seeding Demo Bookings & Reviews...")
        completed_bookings_data = [
            (1, 1, 1, date.today() - timedelta(days=10), time(10, 0), 250.00, 5.0, "Outstanding electrician! Solved the short-circuit issue and installed the ceiling fan flawlessly."),
            (2, 1, 1, date.today() - timedelta(days=8), time(14, 0), 250.00, 4.5, "Very polite and arrived right on time. Clean work."),
            (3, 2, 3, date.today() - timedelta(days=7), time(11, 0), 350.00, 4.0, "Fixed the pipeline leakage and cleared the bathroom drain properly."),
            (4, 3, 5, date.today() - timedelta(days=6), time(9, 30), 450.00, 5.0, "Master craftsman. Assembled my large wooden wardrobe with great precision."),
            (5, 5, 7, date.today() - timedelta(days=5), time(15, 0), 500.00, 4.5, "Diagnosed the washing machine noise quickly and replaced the worn belt."),
            (6, 6, 8, date.today() - timedelta(days=5), time(10, 0), 1200.00, 5.0, "Entire house is sparkling clean. Sanitized kitchen and bathrooms thoroughly."),
            (7, 9, 11, date.today() - timedelta(days=4), time(13, 0), 650.00, 4.5, "AC cooling was restored completely after gas refill and pressure wash."),
            (8, 10, 12, date.today() - timedelta(days=3), time(11, 0), 600.00, 4.0, "Good masonry repair on wall cracks and neat tile fitting."),
            (9, 11, 1, date.today() - timedelta(days=3), time(16, 0), 250.00, 5.0, "Arvind is fantastic! Repaired our switchboard in under 20 minutes."),
            (10, 11, 2, date.today() - timedelta(days=2), time(10, 30), 300.00, 4.8, "Neat electrical work, tested all switches before leaving."),
            (1, 12, 3, date.today() - timedelta(days=2), time(12, 0), 350.00, 3.5, "Fixed the tap leak, arrived 15 mins late but did the job."),
            (2, 16, 8, date.today() - timedelta(days=1), time(9, 0), 1200.00, 5.0, "Very reliable deep home cleaning team."),
            (3, 18, 5, date.today() - timedelta(days=1), time(14, 0), 450.00, 5.0, "Expert carpentry work on door frame."),
        ]

        bookings_added = 0
        for cust_idx, work_idx, svc_idx, b_date, b_time, amt, rating_val, review_txt in completed_bookings_data:
            if cust_idx <= len(cust_objs) and work_idx <= len(worker_objs):
                cust = cust_objs[cust_idx - 1]
                work = worker_objs[work_idx - 1]

                # Check if this booking exists
                existing_booking = db.query(Booking).filter(
                    Booking.customer_id == cust.customer_id,
                    Booking.worker_id == work.worker_id,
                    Booking.service_id == svc_idx,
                    Booking.booking_date == b_date,
                    Booking.start_time == b_time,
                ).first()

                if not existing_booking:
                    booking = Booking(
                        customer_id=cust.customer_id,
                        worker_id=work.worker_id,
                        service_id=svc_idx,
                        booking_date=b_date,
                        start_time=b_time,
                        address=cust.address,
                        description="Completed household trade service order.",
                        amount=amt,
                        estimated_price=amt,
                        service_lat=cust.latitude,
                        service_lon=cust.longitude,
                        status="COMPLETED",
                        payment_status="PAID",
                    )
                    db.add(booking)
                    db.flush()

                    review = RatingReview(
                        booking_id=booking.booking_id,
                        customer_id=cust.customer_id,
                        worker_id=work.worker_id,
                        rating=rating_val,
                        review=review_txt,
                    )
                    db.add(review)
                    bookings_added += 1

        # Active demo bookings
        active_bookings_data = [
            (4, 11, 1, date.today(), time(11, 0), 250.00, "ACCEPTED", "PENDING"),
            (5, 7, 9, date.today(), time(15, 0), 350.00, "PENDING", "PENDING"),
            (6, 1, 2, date.today() + timedelta(days=1), time(10, 0), 300.00, "PENDING", "PENDING"),
            (7, 4, 6, date.today() - timedelta(days=12), time(10, 0), 850.00, "CANCELLED", "REFUNDED"),
        ]

        for cust_idx, work_idx, svc_idx, b_date, b_time, amt, b_status, p_status in active_bookings_data:
            if cust_idx <= len(cust_objs) and work_idx <= len(worker_objs):
                cust = cust_objs[cust_idx - 1]
                work = worker_objs[work_idx - 1]

                existing_b = db.query(Booking).filter(
                    Booking.customer_id == cust.customer_id,
                    Booking.worker_id == work.worker_id,
                    Booking.service_id == svc_idx,
                    Booking.booking_date == b_date,
                ).first()

                if not existing_b:
                    b = Booking(
                        customer_id=cust.customer_id,
                        worker_id=work.worker_id,
                        service_id=svc_idx,
                        booking_date=b_date,
                        start_time=b_time,
                        address=cust.address,
                        description="Active/Pending service request.",
                        amount=amt,
                        estimated_price=amt,
                        service_lat=cust.latitude,
                        service_lon=cust.longitude,
                        status=b_status,
                        payment_status=p_status,
                    )
                    db.add(b)
                    bookings_added += 1

        # ─────────────────────────────────────────────────────
        # 6. SEED COOPERATIVE WELFARE LEDGER (Slide 3 Welfare DB)
        # ─────────────────────────────────────────────────────
        print("[*] Checking & Seeding Cooperative Welfare Ledger...")
        completed_bookings = db.query(Booking).filter(Booking.status.in_(["COMPLETED", "completed"])).all()
        welfare_added = 0
        for b in completed_bookings:
            w_exist = db.query(CooperativeWelfareLedger).filter(CooperativeWelfareLedger.booking_id == b.booking_id).first()
            if not w_exist:
                w_entry = CooperativeWelfareLedger(
                    booking_id=b.booking_id,
                    society_id=1,
                    amount=float(b.welfare_pool_fee or 10.00),
                    entry_type="CREDIT",
                    description=f"Welfare Gullak Contribution from Booking SH-{b.booking_id:04d}",
                )
                db.add(w_entry)
                welfare_added += 1

        db.commit()
        welfare_count = db.query(CooperativeWelfareLedger).count()
        print(f"[OK] Cooperative Welfare Ledger ready: {welfare_count} entries ({welfare_added} newly credited).")

        print("=" * 60)
        print("[SUCCESS] Database seeding completed successfully!")
        print(f"  - Skills: {len(skill_objs)}")
        print(f"  - Services: {len(service_map)}")
        print(f"  - Customers: {len(cust_objs)} (Demo: customer@example.com / Password123!)")
        print(f"  - Workers: {len(worker_objs)} (Demo: worker@example.com / Password123!)")
        print(f"  - Welfare Ledger (Society 1 Gullak): {welfare_count} contributions")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Database seeding failed: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
