"""
migrate_to_supabase.py — Supabase Database Migration & Verification Utility

Usage:
  1. Set your Supabase connection string:
       Windows PowerShell:
         $env:SUPABASE_DATABASE_URL = "postgresql+psycopg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres"
         python migrate_to_supabase.py

  2. Or provide it interactively when prompted.
"""
import os
import sys
from sqlalchemy import create_engine, text
from app.models import Base
from seed import seed_database
from app.database import verify_connection


def run_migration(target_db_url: str):
    print(f"[*] Connecting to Supabase database...")
    try:
        # Create temporary engine for migration
        engine = create_engine(target_db_url, pool_pre_ping=True, echo=False)
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
            print(f"[OK] Supabase connected successfully: {str(version)[:60]}...")

        # Recreate tables in Supabase
        print("[*] Creating 8 database tables and relationships in Supabase...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("[OK] Tables created: customer_data, worker_data, skills, workers_skill, availability, services, bookings, ratings_reviews")

        # Reconnect backend database engine with target url to seed
        os.environ["DATABASE_URL"] = target_db_url
        import app.database
        app.database.DATABASE_URL = target_db_url
        app.database.engine = engine
        from sqlalchemy.orm import sessionmaker
        app.database.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

        print("[*] Seeding Supabase with skills, services, customers, workers, availability, bookings, and reviews...")
        seed_database()

        print("\n[SUCCESS] Supabase migration and data seeding completed successfully!")
        print("  - Set this DATABASE_URL in your Render Environment Variables dashboard:")
        print(f"    DATABASE_URL={target_db_url[:25]}... (redacted)")

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    supabase_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not supabase_url or "localhost" in supabase_url:
        print("\n========================================================")
        print("   Sahāyu Supabase PostgreSQL Migration Utility")
        print("========================================================")
        print("Enter your Supabase PostgreSQL connection string.")
        print("Format: postgresql+psycopg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres")
        print("Or:     postgresql+psycopg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres\n")
        
        entered_url = input("Supabase Connection URL: ").strip()
        if not entered_url:
            print("[ABORTED] No connection string provided.")
            sys.exit(1)
        supabase_url = entered_url

    run_migration(supabase_url)
