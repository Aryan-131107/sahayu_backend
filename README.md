# Cooperative Gig Services Platform for Household & Community Services
### Smart India Hackathon (SIH 2026) — Problem Statement 26089

A transparent, cooperative gig services backend designed with explainable matching AI, strict state-machine lifecycle enforcement, double-booking prevention, 1-to-1 review integrity, and role-guarded JWT authentication.

---

## 🏛 Architecture & Tech Stack

```
+------------------------------------------------------------------------------------+
|                         FastAPI REST & API Gateway (/api)                          |
+------------------------------------------------------------------------------------+
           |                         |                         |
+---------------------+   +---------------------+   +---------------------+
|  Auth & JWT Security|   | Explainable Matching|   | Booking State Engine|
|  - Bcrypt Hashing   |   | - 6-Param Formula   |   | - Overlap Guard     |
|  - Role Separation  |   | - 0-100 Normalizer  |   | - Review Integrity  |
|  - 401/403 Guards   |   | - Explain Reasons   |   | - Dynamic Paid/Free |
+---------------------+   +---------------------+   +---------------------+
           \                         |                         /
            +-------------------------------------------------+
            |       SQLAlchemy 2.0 ORM & PostgreSQL DB        |
            +-------------------------------------------------+
```

- **Backend Framework**: Python 3.11+ / 3.14, FastAPI, Uvicorn
- **Database**: PostgreSQL with SQLAlchemy 2.0 ORM & Psycopg 3
- **Security & Auth**: PyJWT, Bcrypt, Passlib
- **Data Validation**: Pydantic v2
- **Testing**: Pytest (51 automated test cases with 100% pass rate)

---

## 🧮 Explainable Rule-Based Matching Engine

Recommendations are calculated transparently with the following formula:

$$\text{matching\_score} = 0.35 \times \text{skill} + 0.20 \times \text{availability} + 0.15 \times \text{experience} + 0.15 \times \text{rating} + 0.10 \times \text{distance} + 0.05 \times \text{price}$$

### Normalization & Sub-Scores:
1. **Skill Match ($35\%$)**: $100$ for Expert certified match, $90$ for Intermediate.
2. **Availability ($20\%$)**: $100$ if available in target slot, $0$ if busy.
3. **Experience ($15\%$)**: $\min(\text{years} / 15, 1.0) \times 100$.
4. **Rating ($15\%$)**: $((\text{avg\_rating} - 1.0) / 4.0) \times 100$ (default $75$ for new workers).
5. **Distance ($10\%$)**: $\max(0, 1 - \text{distance\_km} / 50.0) \times 100$ using Haversine formula.
6. **Price ($5\%$)**: Normalized against service market benchmark.

Each recommendation includes a structured `reasons` list detailing the exact justification for the score.

---

## 🔑 Demo Login Accounts (Pre-Seeded)

| Role | Email | Password | Details |
|---|---|---|---|
| **Customer** | `customer@example.com` | `Password123!` | Pre-seeded with address in Jabalpur & historical orders |
| **Worker** | `worker@example.com` | `Password123!` | Electrician & AC Technician (8 yrs exp, 5.0 avg rating) |

---

## 🚀 Quickstart & Setup Guide

### 1. Clone & Setup Virtual Environment
```bash
git clone <repo-url>
cd sih_project/backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure `DATABASE_URL` points to your PostgreSQL instance:
```env
DATABASE_URL=postgresql+psycopg://postgres:sih2025admin@localhost:5432/gig_services
```

### 3. Initialize & Seed Database
```bash
python seed.py
```
*Seeds 12 skills, 12 services, 10 customers, 20 workers, availability slots, completed/pending bookings, and reviews.*

### 4. Start Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
- **Swagger Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Running Automated Tests

```bash
pytest tests/ -v
```
All **51 unit and integration tests** cover:
- Customer & Worker Registration & Login
- Double-Booking Prevention & Skill validation
- State machine lifecycle (`PENDING` $\to$ `ACCEPTED` $\to$ `IN_PROGRESS` $\to$ `COMPLETED`)
- 1-to-1 Review constraints & worker average rating recalculations
- Matching Engine 6-parameter formula verification
- Cross-account 401 Unauthorized / 403 Forbidden security guards

---

## 📡 REST API Catalog

### 🔐 Authentication (`/api/auth`)
- `POST /api/auth/register/customer` — Register a customer account
- `POST /api/auth/register/worker` — Register a worker profile with skills
- `POST /api/auth/login` — Unified login returning signed JWT
- `GET /api/auth/me` — Retrieve profile of authenticated user

### 👥 Customers (`/api/customers`)
- `GET /api/customers/{id}` — Fetch customer profile
- `PUT /api/customers/{id}` — Update profile (Role protected)

### 🛠 Workers (`/api/workers`)
- `GET /api/workers` — List workers with filters (`city`, `skill`, `active_only`)
- `GET /api/workers/{id}` — Get worker profile with skills and ratings
- `PUT /api/workers/{id}` — Update profile (Role protected)
- `POST /api/workers/{id}/skills` — Attach certified skill
- `DELETE /api/workers/{id}/skills/{skill_id}` — Detach skill
- `PATCH /api/workers/{id}/availability` — Toggle real-time availability
- `GET /api/workers/recommend` — Recommendation ranking

### 📅 Availability & Slots (`/api/availability`)
- `GET /api/availability/{worker_id}` — List availability calendar slots
- `POST /api/availability` — Create a worker availability slot
- `PATCH /api/availability/{worker_id}/toggle` — Toggle status
- `DELETE /api/availability/{slot_id}` — Remove slot

### 📋 Bookings (`/api/bookings`)
- `POST /api/bookings` — Create a booking (Double-booking protected)
- `GET /api/bookings/{id}` — Get single booking details
- `GET /api/bookings/customer/{customer_id}` — Customer booking history
- `GET /api/bookings/worker/{worker_id}` — Worker incoming booking feed
- `PATCH /api/bookings/{id}/accept` — Accept booking
- `PATCH /api/bookings/{id}/reject` — Reject booking
- `PATCH /api/bookings/{id}/start` — Start job (IN_PROGRESS)
- `PATCH /api/bookings/{id}/complete` — Complete job & release worker
- `PATCH /api/bookings/{id}/cancel` — Cancel booking

### ⭐ Reviews (`/api/reviews`)
- `POST /api/reviews` — Submit review for completed booking (1-to-1)
- `GET /api/reviews/{booking_id}` — Get booking review
- `GET /api/workers/{worker_id}/reviews` — List reviews & rating aggregates

### 🎯 Explainable Matching (`/api/matching`)
- `GET /api/matching/recommendations` — Explainable recommendations with sub-score breakdown and reasoning array.
