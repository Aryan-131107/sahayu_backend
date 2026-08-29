# Render Deployment & Supabase PostgreSQL Setup Guide

## 1. Supabase PostgreSQL Migration (Step-by-Step)

### Option A: Using the Supabase SQL Editor (Recommended - 1 Minute)
1. Go to your [Supabase Dashboard](https://supabase.com/dashboard) and open your project.
2. Click on the **SQL Editor** tab in the left sidebar.
3. Click **New Query**.
4. Copy the entire contents of [`database/supabase_migration.sql`](../database/supabase_migration.sql) and paste it into the editor.
5. Click **Run**. All 8 tables, indexes, constraints, and realistic seed data (skills, services, demo accounts, workers, bookings, reviews) will be created immediately.

### Option B: Using the Migration Script
Run the automated migration helper from your terminal:
```bash
python migrate_to_supabase.py
```
*(Enter your Supabase connection string when prompted).*

---

## 2. Getting Your Supabase Connection String
1. In the Supabase Dashboard, click **Project Settings** (gear icon at bottom left) -> **Database**.
2. Scroll to **Connection string** -> select the **URI** tab.
3. Choose either:
   - **Transaction Pooler (Port 6543)** *(Recommended for Render)*:
     `postgresql+psycopg://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres`
   - **Session Pooler (Port 5432)**:
     `postgresql+psycopg://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres`
   - **Direct Connection (Port 5432)**:
     `postgresql+psycopg://postgres:[YOUR_PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres`
4. Replace `[YOUR_PASSWORD]` with your actual database password.
5. **Important**: Prefix with `postgresql+psycopg://` so SQLAlchemy uses the modern `psycopg` v3 driver.

---

## 3. Render Web Service Configuration

- **Type**: Web Service
- **Runtime**: Python 3
- **Root Directory**: `backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`

---

## 4. Environment Variables on Render Dashboard

Set the following in your Render Web Service -> **Environment** tab:

| Variable Name | Required | Value / Instructions |
|---|---|---|
| `DATABASE_URL` | **Yes** | Your Supabase connection string (`postgresql+psycopg://...`) |
| `SECRET_KEY` | **Yes** | 32+ character random string for JWT token signing |
| `ALLOWED_ORIGINS` | No | Comma-separated frontend domains (e.g. `https://sahayu.vercel.app,http://localhost:3000`) |
| `ENVIRONMENT` | No | `production` |
| `ALGORITHM` | No | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `10080` (7 days) |

---

## 5. Verifying the Deployment
Once deployed on Render:
- Test Health: `GET https://your-service.onrender.com/health` -> `{"status": "healthy", "database": "connected"}`
- Test Swagger Docs: `https://your-service.onrender.com/docs`
- Demo Customer Login: `customer@example.com` / `Password123!`
- Demo Worker Login: `worker@example.com` / `Password123!`
