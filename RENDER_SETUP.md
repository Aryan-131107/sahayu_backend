# Render Deployment Configuration

## Service Type
- **Type**: Web Service
- **Runtime**: Python 3
- **Root Directory**: `backend`

## Build & Start Commands
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Health Check
- **Health Check Path**: `/health`

## Environment Variables Required

| Variable Name | Description / Requirement |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+psycopg://user:password@host:port/dbname`) |
| `SECRET_KEY` | Strong random secret key for JWT token signing |
| `ALGORITHM` | (Optional, default `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | (Optional, default `10080`) |
| `ALLOWED_ORIGINS` | (Optional) Comma-separated allowed frontend domains (e.g. `https://your-app.vercel.app`) |
| `ENVIRONMENT` | (Optional, default `production`) |
| `APP_TITLE` | (Optional, default `Cooperative Gig Services API`) |
| `APP_VERSION` | (Optional, default `1.0.0`) |

## Database Seeding (First-time / Manual)
To seed initial trade skills, services, and demo data into the PostgreSQL database, run the following one-off command from the Render Shell tab:
```bash
python seed.py
```
*(Do not include `python seed.py` in the Build Command to avoid re-seeding and overwriting live data on each build).*
