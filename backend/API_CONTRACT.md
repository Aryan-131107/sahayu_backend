# Sahāyu API Contract (SIH 2026 - PS 26089)

**Base URL**: `http://localhost:8000` (or `/api`)
**Auth**: `Authorization: Bearer <access_token>`

## Authentication & User Endpoints
- `POST /auth/register` | Register customer or worker | Body: `{name, phone, email, password, role: "customer"|"worker", [experience_years, hourly_rate, skill_ids]}` | Resp: `{access_token, token_type, user_type, user}` | 201 | Auth: No
- `POST /auth/login` | Login user | Body: `{email, password, [role]}` | Resp: `{access_token, token_type, user_type, user}` | 200/401 | Auth: No
- `GET /auth/me` | Current authenticated user profile | Resp: `{id, name, email, phone, role, city, address}` | 200/401 | Auth: Yes
- `GET /customers/me` | Current customer profile | Resp: `{customer_id, name, phone, email, address, city, ...}` | 200/401/403 | Auth: Customer
- `GET /workers/me` | Current worker profile | Resp: `{worker_id, name, phone, email, hourly_rate, skills, ...}` | 200/401/403 | Auth: Worker

## Catalog & Workers
- `GET /skills` | List vocational trade skills | Resp: `[{skill_id, skill_name, description}]` | 200 | Auth: No
- `GET /services` | List service offerings | Query: `category, skill_id` | Resp: `[{service_id, service_name, base_price, skill_id, skill}]` | 200 | Auth: No
- `GET /services/{id}` | Get single service details | Resp: `{service_id, service_name, base_price, ...}` | 200/404 | Auth: No
- `GET /workers` | List active workers | Query: `city, skill, active_only` | Resp: `[{worker_id, name, hourly_rate, skills, average_rating}]` | 200 | Auth: No
- `GET /workers/{id}` | Get worker profile | Resp: `{worker_id, name, phone, email, hourly_rate, skills, average_rating, ...}` | 200/404 | Auth: No
- `GET /workers/search` | Search workers by skill | Query: `skill` | Resp: `[{worker_id, name, skills, ...}]` | 200/404 | Auth: No
- `GET /workers/recommend` | Ranked matching workers | Query: `service_id, latitude, longitude, top_n, [city]` | Resp: `{service_id, total_found, recommendations: [{worker_id, name, matching_score, score_breakdown, reasons}]}` | 200 | Auth: No
- `PATCH /workers/{id}/availability` | Toggle availability | Body: `{is_available: bool}` | Resp: `{worker_id, is_available, ...}` | 200/403 | Auth: Worker (Self)

## Bookings & State Lifecycle
- `POST /bookings` | Create booking | Body: `{[customer_id], worker_id, service_id, amount, [booking_date, start_time, address, description]}` | Resp: `{booking_id, status: "PENDING", ...}` | 201/400/409 | Auth: Customer (optional)
- `GET /bookings/customer/me` | Logged-in customer booking history | Query: `status_filter` | Resp: `[{booking_id, status, worker_name, amount, ...}]` | 200/401/403 | Auth: Customer
- `GET /bookings/worker/me` | Logged-in worker incoming booking feed | Query: `status_filter` | Resp: `[{booking_id, status, customer_name, amount, ...}]` | 200/401/403 | Auth: Worker
- `GET /bookings/{id}` | Get single booking details | Resp: `{booking_id, status, payment_status, ...}` | 200/404 | Auth: No
- `PATCH /bookings/{id}/accept` | Accept pending booking | Resp: `{booking_id, status: "ACCEPTED"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/reject` | Reject pending booking | Resp: `{booking_id, status: "REJECTED"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/start` | Start accepted booking | Resp: `{booking_id, status: "IN_PROGRESS"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/complete` | Mark complete & paid | Resp: `{booking_id, status: "COMPLETED", payment_status: "PAID"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/cancel` | Cancel booking | Resp: `{booking_id, status: "CANCELLED"}` | 200/409 | Auth: Customer/Worker

## Reviews & System
- `POST /reviews` | Submit 1-to-1 review for COMPLETED booking | Body: `{booking_id, [customer_id], rating: 1.0-5.0, review}` | Resp: `{review_id, rating, review}` | 201/400/409 | Auth: Customer
- `GET /reviews/{booking_id}` | Get review for booking | Resp: `{review_id, rating, review}` | 200/404 | Auth: No
- `GET /workers/{id}/reviews` | List worker reviews & avg rating | Resp: `{worker_id, average_rating, total_reviews, reviews: [...]}` | 200/404 | Auth: No
- `GET /health` | System health check | Resp: `{status: "healthy", database: "connected", postgres_version}` | 200 | Auth: No

## Core User Flows
1. **Customer Flow**:
   `POST /auth/register` (or `POST /auth/login`) -> `GET /services` -> `GET /workers/recommend?service_id=...` -> `POST /bookings` -> Track `GET /bookings/customer/me` -> `POST /reviews` after completion.
2. **Worker Flow**:
   `POST /auth/login` -> `GET /workers/me` -> `GET /bookings/worker/me` -> `PATCH /bookings/{id}/accept` -> `PATCH /bookings/{id}/start` -> `PATCH /bookings/{id}/complete`.
