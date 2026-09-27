"""
app/core/security.py — Password Hashing & JWT Token Utilities
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import jwt
import bcrypt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    try:
        if not hashed_password or not plain_password:
            return False
        clean_hash = hashed_password.strip()
        # If hashed with bcrypt ($2a$, $2b$, $2y$, $2x$)
        if clean_hash.startswith(("$2b$", "$2a$", "$2y$", "$2x$", "$2")):
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                clean_hash.encode("utf-8")
            )
        # Fallback for plain text demo accounts if any
        return plain_password == clean_hash
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


# ── Token Revocation / Logout Session Blacklist ─────────────────────────
_revoked_tokens: Dict[str, datetime] = {}


def revoke_token(token: str) -> bool:
    """Revoke an active JWT access token to invalidate the session."""
    if not token:
        return False
    token_clean = token.strip()
    if token_clean.lower().startswith("bearer "):
        token_clean = token_clean[7:].strip()
    if not token_clean:
        return False

    payload = decode_access_token(token_clean)
    if payload and "exp" in payload:
        try:
            exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        except Exception:
            exp_time = datetime.now(timezone.utc) + timedelta(days=7)
    else:
        exp_time = datetime.now(timezone.utc) + timedelta(days=7)

    _revoked_tokens[token_clean] = exp_time

    # Prune expired tokens periodically
    now = datetime.now(timezone.utc)
    expired_keys = [k for k, v in _revoked_tokens.items() if v < now]
    for k in expired_keys:
        _revoked_tokens.pop(k, None)

    return True


def is_token_revoked(token: str) -> bool:
    """Check if a token has been revoked / logged out."""
    if not token:
        return False
    token_clean = token.strip()
    if token_clean.lower().startswith("bearer "):
        token_clean = token_clean[7:].strip()
    return token_clean in _revoked_tokens


def clear_revoked_tokens() -> None:
    """Clear revoked token store (used in test setup if needed)."""
    _revoked_tokens.clear()

