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
- `POST /bookings` | Standard booking creation | Body: `{[customer_id], worker_id, service_id, amount, [booking_date, start_time, address, description]}` | Resp: `{booking_id, status: "PENDING", ...}` | 201/400/409 | Auth: Customer (optional)
- `POST /bookings/create` | Dual-OTP Slide 3 Booking Initialization | Body: `{[customer_id], worker_id, [service_id], [service_scope], [location], [booking_date], [start_time]}` | Resp: `{booking_id, booking_reference: "SH-0060", start_otp: "4821", end_otp: "9134", pricing: {worker_payout: 199.00, platform_tech_fee: 30.00, welfare_pool_fee: 10.00, total_amount: 239.00}, status: "pending"}` | 201 | Auth: Customer (optional)
- `POST /bookings/verify-start-otp` | Doorstep Arrival Verification (PIN 4821) | Body: `{booking_id, otp: "4821"}` | Resp: `{booking_id, booking_reference, status: "in_progress", arrival_confirmed: true}` | 200/400/404 | Auth: Optional
- `POST /bookings/verify-end-otp` | Job Completion Settlement & 72h Warranty (PIN 9134) | Body: `{booking_id, otp: "9134"}` | Resp: `{booking_id, booking_reference, status: "completed", settlement_summary: {worker_payout_released: 199.00, welfare_gullak_credited: 10.00, platform_tech_fee_retained: 30.00, total_settled: 239.00}, warranty_active: true, warranty_expires_at}` | 200/400/404 | Auth: Optional
- `GET /bookings/welfare-fund/summary` | Society Gullak Welfare Reserve Summary (Slide 3 Welfare DB) | Query: `society_id=1` | Resp: `{society_id: 1, total_gullak_reserve, total_contributions_count, governing_body: "Jabalpur District Cooperative Federation", currency: "INR"}` | 200 | Auth: No
- `GET /bookings/customer/me` | Logged-in customer booking history | Query: `status_filter` | Resp: `[{booking_id, status, worker_name, amount, ...}]` | 200/401/403 | Auth: Customer
- `GET /bookings/worker/me` | Logged-in worker incoming booking feed | Query: `status_filter` | Resp: `[{booking_id, status, customer_name, amount, ...}]` | 200/401/403 | Auth: Worker
- `GET /bookings/{id}` | Get single booking details | Resp: `{booking_id, status, payment_status, ...}` | 200/404 | Auth: No
- `PATCH /bookings/{id}/accept` / `POST /bookings/{id}/accept` | Accept booking (with terminal override for demo) | Resp: `{booking_id, status: "ACCEPTED"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/reject` / `POST /bookings/{id}/reject` | Reject pending booking | Resp: `{booking_id, status: "REJECTED"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/start` / `POST /bookings/{id}/start` | Start accepted booking | Resp: `{booking_id, status: "IN_PROGRESS"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/complete` / `POST /bookings/{id}/complete` | Mark complete & paid | Resp: `{booking_id, status: "COMPLETED", payment_status: "PAID"}` | 200/409 | Auth: Worker
- `PATCH /bookings/{id}/cancel` / `POST /bookings/{id}/cancel` | Cancel booking | Resp: `{booking_id, status: "CANCELLED"}` | 200/409 | Auth: Customer/Worker
- `PATCH /bookings/{id}/status` | Direct status update with demo bypass | Query: `status` | Resp: `{booking_id, status, ...}` | 200/409 | Auth: Optional
- `GET /bookings/reference/{ref}` | Lookup booking by reference (e.g. SH-0058) | Resp: `{booking_id, ...}` | 200/404 | Auth: No
- `POST /demo/reset` (or `POST /api/demo/reset`) | Forcefully reset active demo order (SH-0058) bypassing terminal locks | Body: `{[booking_id], [booking_reference]}` | Resp: `{success: true, message, booking_id, status: "ASSIGNED", start_otp: "4821", end_otp: "9134", booking: {...}}` | 200 | Auth: No
- `POST /demo/cycle-scenario` (or `POST /api/demo/cycle-scenario`, `POST /demo/cycle`) | Rotates through 5 trade scenarios (0: Electrical, 1: Gardening, 2: Plumbing, 3: Carpentry, 4: HVAC) with clean state reset | Body/Query: `{[scenario_index: 0..4], [booking_id]}` | Resp: `BookingResponse` | 200 | Auth: No
- `POST /demo/new-booking` (or `POST /api/demo/new-booking`) | Create a new randomized demo booking from pre-seeded service sets | Resp: `{booking_id, booking_reference, status: "ASSIGNED", payment_status: "UNPAID", start_otp: "4821", end_otp: "9134", ...}` | 201 | Auth: No
- `POST /bookings/{id}/demo-pay` | Instant simulated UPI/Card payment & settlement | Body: `{booking_id, [payment_method]}` | Resp: `{success: true, payment_status: "paid", settlement_summary, warranty_active: true}` | 200 | Auth: No

## Reviews & System
- `POST /reviews` | Submit 1-to-1 review for COMPLETED booking | Body: `{booking_id, [customer_id], rating: 1.0-5.0, review}` | Resp: `{review_id, rating, review}` | 201/400/409 | Auth: Customer
- `GET /reviews/{booking_id}` | Get review for booking | Resp: `{review_id, rating, review}` | 200/404 | Auth: No
- `GET /workers/{id}/reviews` | List worker reviews & avg rating | Resp: `{worker_id, average_rating, total_reviews, reviews: [...]}` | 200/404 | Auth: No
- `GET /health` | System health check | Resp: `{status: "healthy", database: "connected", postgres_version}` | 200 | Auth: No

## Demo Shramik / e-Shram Worker Verification
- `POST /workers/verify` | Submit worker for demo Shramik verification | Body: `{[worker_id], shramik_id, [skill], [skill_certificate], [verification_type]}` | Resp: `{worker_id, name, shramik_id, verification_status: "PENDING", ...}` | 200/400/409 | Auth: Worker (optional if worker_id passed)
- `GET /workers/{id}/verification` | Get worker verification status | Resp: `{worker_id, name, shramik_id, verification_status, verified_at, is_verified}` | 200/404 | Auth: No

## Bhashini AI Voice Assistant (Worker Dashboard)
- `POST /voice/transcribe` (or `POST /api/voice/transcribe`) | Transcribe Hindi speech audio to text (Bhashini ASR) | Body: Multipart Form (`file: UploadFile`, `[language="hi"]`) | Resp: `{success: bool, [text]: str, [language]: "hi", [error]: str}` | 200 | Auth: No
- `POST /voice/speak` (or `POST /api/voice/speak`) | Synthesize Hindi text into spoken audio (Bhashini TTS) | Body: `{text: str, [language="hi"], [gender="female"], [speed=1.0]}` | Resp: `{success: bool, [audio_base64]: str, [audio_format]: "wav", [mime_type]: "audio/wav", [data_url]: str, [error]: str}` | 200 | Auth: No
- `GET /voice/status` (or `GET /api/voice/status`) | Diagnostic status of Bhashini voice module (no secrets leaked) | Resp: `{success: bool, is_configured: bool, supported_language: "hi", pipeline_id: str, cached_asr: bool, cached_tts: bool}` | 200 | Auth: No (Role: Admin)

## Admin Dashboard (Role: Admin)
- `GET /admin/stats` | Platform aggregates (workers, customers, bookings, payments, fees, earnings) | Resp: `{total_workers, verified_workers, pending_workers, total_bookings, completed_bookings, total_customer_payments, total_worker_earnings, total_platform_fees, total_revenue}` | 200/401/403 | Auth: Admin
- `GET /admin/workers` | Filter & search workers | Query: `search, verification_status, is_active, skill_id, city` | Resp: `[{worker_id, name, phone, email, shramik_id, verification_status, is_active, skills, ...}]` | 200/401/403 | Auth: Admin
- `PATCH /admin/workers/{id}/status` | Activate/deactivate worker | Body: `{is_active: bool}` | Resp: `{worker_id, is_active, ...}` | 200/401/403 | Auth: Admin
- `GET /admin/verifications` | List pending worker verifications | Resp: `[{worker_id, name, shramik_id, verification_status: "PENDING", ...}]` | 200/401/403 | Auth: Admin
- `GET /admin/workers/{id}/verification` | View worker verification details | Resp: `{worker_id, name, shramik_id, verification_status, ...}` | 200/401/403 | Auth: Admin
- `PATCH /admin/workers/{id}/verify` | Approve and mark worker as VERIFIED | Resp: `{worker_id, verification_status: "VERIFIED", is_verified: true, verified_at, ...}` | 200/401/403 | Auth: Admin
- `PATCH /admin/workers/{id}/reject` | Reject worker verification | Body: `{[rejection_reason]}` | Resp: `{worker_id, verification_status: "REJECTED", is_verified: false, ...}` | 200/401/403 | Auth: Admin
- `GET /admin/bookings` | All bookings with transparent payment breakdown (Customer Payment = Platform Fee + Worker Earnings) | Query: `status_filter, payment_status, worker_id, customer_id` | Resp: `[{booking_id, customer, worker, service, amount, customer_paid_amount, platform_fee, worker_earnings, payment_breakdown: {...}}]` | 200/401/403 | Auth: Admin
- `GET /admin/payments` | Dedicated payment transaction history | Resp: `[{booking_id, customer_name, worker_name, service_name, customer_paid_amount, platform_fee, worker_earnings, payment_status, payment_date}]` | 200/401/403 | Auth: Admin
- `GET /admin/services` | Service catalog offerings | Resp: `[{service_id, service_name, base_price, is_active, skill, ...}]` | 200/401/403 | Auth: Admin
- `POST /admin/services` | Create new service offering | Body: `{service_name, description, category, base_price, estimated_duration, skill_id}` | Resp: `{service_id, ...}` | 201/401/403 | Auth: Admin
- `PATCH /admin/services/{id}` | Update service catalog offering | Body: `{[service_name], [description], [base_price], [is_active], [skill_id], ...}` | Resp: `{service_id, ...}` | 200/401/403 | Auth: Admin
- `GET /admin/reviews` | List all platform reviews with customer & worker names | Resp: `[{review_id, booking_id, customer_name, worker_name, service_name, rating, review}]` | 200/401/403 | Auth: Admin

## Core User Flows
1. **Customer Flow**:
   `POST /auth/register` (or `POST /auth/login`) -> `GET /services` -> `GET /workers/recommend?service_id=...` -> `POST /bookings` -> Track `GET /bookings/customer/me` -> `POST /reviews` after completion.
2. **Worker Flow**:
   `POST /auth/login` -> `GET /workers/me` -> `POST /workers/verify` (submit Shramik ID) -> `GET /bookings/worker/me` -> `PATCH /bookings/{id}/accept` -> `PATCH /bookings/{id}/start` -> `PATCH /bookings/{id}/complete`.
3. **Admin Flow**:
   `POST /auth/login` (admin@example.com) -> `GET /admin/stats` -> `GET /admin/verifications` -> `PATCH /admin/workers/{id}/verify` -> `GET /admin/bookings` (monitor fee & earnings).
