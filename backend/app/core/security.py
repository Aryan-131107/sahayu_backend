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
