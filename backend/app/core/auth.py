"""
app/core/auth.py — Authentication & Role-Based Authorization Dependencies
"""
from typing import Optional, Union, Dict, Any
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token
from app.models import CustomerData, WorkerData

# Token URL for swagger docs
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    id: int
    email: Optional[str] = None
    role: str  # "customer" or "worker"
    name: str

    model_config = {"from_attributes": True}


def get_current_token(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    token_str: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """Extract token from either Bearer authorization header or OAuth2 form."""
    if bearer and bearer.credentials:
        return bearer.credentials
    if token_str:
        return token_str
    return None


def get_current_user(
    token: Optional[str] = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> AuthUser:
    """
    Validate JWT token and return authenticated user object.
    Raises 401 Unauthorized if token is missing or invalid.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub") or payload.get("user_id")
    role = payload.get("role") or payload.get("user_type")

    if not user_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing user identity or role.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if role == "customer":
        customer = db.get(CustomerData, user_id_int)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Customer account no longer exists.",
            )
        return AuthUser(
            id=customer.customer_id,
            email=customer.email,
            role="customer",
            name=customer.name,
        )
    elif role == "worker":
        worker = db.get(WorkerData, user_id_int)
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Worker account no longer exists.",
            )
        return AuthUser(
            id=worker.worker_id,
            email=worker.email,
            role="worker",
            name=worker.name,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unknown role '{role}' in token.",
        )


def get_optional_current_user(
    token: Optional[str] = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> Optional[AuthUser]:
    """Optional auth for public endpoints that offer extra features when logged in."""
    if not token:
        return None
    try:
        return get_current_user(token=token, db=db)
    except HTTPException:
        return None


def require_customer(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Enforce that the authenticated user is a customer."""
    if current_user.role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to customer accounts only.",
        )
    return current_user


def require_worker(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Enforce that the authenticated user is a worker."""
    if current_user.role != "worker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to worker accounts only.",
        )
    return current_user
