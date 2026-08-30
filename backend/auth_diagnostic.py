"""
auth_diagnostic.py — Safe login diagnostic for Sahayu backend.
Reports ONLY: user_found, password_verification, failure_reason.
Does NOT print password, hash, SECRET_KEY, or DATABASE_URL.

Run from backend/ directory with DATABASE_URL set:
    python auth_diagnostic.py

On Render, you can run this as a one-off job:
    cd /opt/render/project/src/backend && python auth_diagnostic.py
"""
import os
import sys

# Allow running from outside backend/ dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_EMAIL = "customer@example.com"
TEST_PASSWORD = "Password123!"
WORKER_EMAIL = "worker@example.com"

def run_diagnostic():
    print("=" * 55)
    print("  Sahayu Auth Diagnostic")
    print("=" * 55)

    # 1. Check environment
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[FAIL] DATABASE_URL is not set")
        return
    masked = db_url[:20] + "...(redacted)" if len(db_url) > 20 else "(set)"
    print(f"[OK]   DATABASE_URL present: {masked}")

    # 2. Import app modules
    try:
        from app.database import SessionLocal
        from app.models import CustomerData, WorkerData
        from app.core.security import verify_password, get_password_hash
        from sqlalchemy import func
        print("[OK]   App modules imported successfully")
    except Exception as e:
        print(f"[FAIL] Import error: {e}")
        return

    # 3. Check bcrypt
    try:
        import bcrypt
        print(f"[OK]   bcrypt version: {bcrypt.__version__}")
        test_hash = get_password_hash("test")
        is_bcrypt = test_hash.startswith("$2b$") or test_hash.startswith("$2a$")
        print(f"[OK]   Hash format is bcrypt: {is_bcrypt}")
        round_trip = verify_password("test", test_hash)
        print(f"[OK]   bcrypt round-trip verify: {round_trip}")
        if not round_trip:
            print("[FAIL] bcrypt round-trip failed — hashing library broken!")
            return
    except Exception as e:
        print(f"[FAIL] bcrypt error: {e}")
        return

    db = SessionLocal()
    try:
        # 4. Customer diagnosis
        print()
        print("--- Customer Account Diagnostic ---")
        c = db.query(CustomerData).filter(
            func.lower(CustomerData.email) == TEST_EMAIL.lower()
        ).first()
        if not c:
            print(f"  user_found:            False")
            print(f"  failure_reason:        customer@example.com NOT in database")
        else:
            print(f"  user_found:            True")
            pw = c.password_hash or ""
            is_bcrypt_hash = pw.startswith("$2b$") or pw.startswith("$2a$")
            print(f"  hash_is_bcrypt:        {is_bcrypt_hash}")
            print(f"  hash_length:           {len(pw)} chars (expected 60)")
            if not pw:
                print(f"  password_verification: False")
                print(f"  failure_reason:        password_hash is NULL/empty in database")
            elif not is_bcrypt_hash:
                print(f"  password_verification: False")
                print(f"  failure_reason:        password_hash is NOT bcrypt (plain text or wrong format)")
            else:
                verified = verify_password(TEST_PASSWORD, pw)
                print(f"  password_verification: {verified}")
                if verified:
                    print(f"  failure_reason:        None — login should work!")
                else:
                    print(f"  failure_reason:        verify_password returned False — hash was generated differently")

        # 5. Worker diagnosis
        print()
        print("--- Worker Account Diagnostic ---")
        w = db.query(WorkerData).filter(
            func.lower(WorkerData.email) == WORKER_EMAIL.lower()
        ).first()
        if not w:
            print(f"  user_found:            False")
            print(f"  failure_reason:        worker@example.com NOT in database")
        else:
            print(f"  user_found:            True")
            pw = w.password_hash or ""
            is_bcrypt_hash = pw.startswith("$2b$") or pw.startswith("$2a$")
            print(f"  hash_is_bcrypt:        {is_bcrypt_hash}")
            print(f"  hash_length:           {len(pw)} chars (expected 60)")
            if not pw:
                print(f"  password_verification: False")
                print(f"  failure_reason:        password_hash is NULL/empty in database")
            elif not is_bcrypt_hash:
                print(f"  password_verification: False")
                print(f"  failure_reason:        password_hash is NOT bcrypt (plain text or wrong format)")
            else:
                verified = verify_password(TEST_PASSWORD, pw)
                print(f"  password_verification: {verified}")
                if verified:
                    print(f"  failure_reason:        None — login should work!")
                else:
                    print(f"  failure_reason:        verify_password returned False — hash was generated differently")

    except Exception as e:
        print(f"[FAIL] Database error: {e}")
    finally:
        db.close()

    print()
    print("=" * 55)


if __name__ == "__main__":
    run_diagnostic()
