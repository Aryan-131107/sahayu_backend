"""
routers/auth.py — Authentication Endpoints for Customers and Workers
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import CustomerData, WorkerData, Skill, WorkerSkill
from app.schemas import (
    RegisterRequest, CustomerRegister, WorkerRegister, LoginRequest, TokenResponse, UserProfile
)
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.auth import get_current_user, AuthUser

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Unified registration for Customer or Worker",
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account as either 'customer' or 'worker'."""
    role_clean = payload.role.strip().lower()
    email_clean = payload.email.strip().lower()

    if role_clean == "worker":
        if db.query(WorkerData).filter(func.lower(WorkerData.email) == email_clean).first():
            raise HTTPException(status_code=409, detail="A worker with this email already exists.")
        if db.query(WorkerData).filter(WorkerData.phone == payload.phone).first():
            raise HTTPException(status_code=409, detail="A worker with this phone number already exists.")

        worker = WorkerData(
            name=payload.name,
            phone=payload.phone,
            email=email_clean,
            password_hash=get_password_hash(payload.password),
            experience_years=payload.experience_years or 0,
            hourly_rate=payload.hourly_rate or 250.00,
            address=payload.address,
            city=payload.city or "Jabalpur",
            latitude=payload.latitude or 23.185000,
            longitude=payload.longitude or 79.982000,
            is_verified=True,
            is_active=True,
        )
        db.add(worker)
        db.flush()

        if payload.skill_ids:
            for skill_id in payload.skill_ids:
                skill = db.get(Skill, skill_id)
                if skill:
                    ws = WorkerSkill(worker_id=worker.worker_id, skill_id=skill_id, skill_level="Intermediate")
                    db.add(ws)

        db.commit()
        db.refresh(worker)

        token = create_access_token(data={"sub": str(worker.worker_id), "role": "worker", "email": worker.email})
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_type="worker",
            user=UserProfile(
                id=worker.worker_id,
                name=worker.name,
                email=worker.email,
                phone=worker.phone,
                role="worker",
                city=worker.city,
                address=worker.address,
            )
        )

    else:
        # Default role is customer
        if db.query(CustomerData).filter(func.lower(CustomerData.email) == email_clean).first():
            raise HTTPException(status_code=409, detail="A customer with this email already exists.")
        if db.query(CustomerData).filter(CustomerData.phone == payload.phone).first():
            raise HTTPException(status_code=409, detail="A customer with this phone number already exists.")

        customer = CustomerData(
            name=payload.name,
            phone=payload.phone,
            email=email_clean,
            password_hash=get_password_hash(payload.password),
            address=payload.address,
            city=payload.city or "Jabalpur",
            latitude=payload.latitude or 23.181500,
            longitude=payload.longitude or 79.986400,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        token = create_access_token(data={"sub": str(customer.customer_id), "role": "customer", "email": customer.email})
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user_type="customer",
            user=UserProfile(
                id=customer.customer_id,
                name=customer.name,
                email=customer.email,
                phone=customer.phone,
                role="customer",
                city=customer.city,
                address=customer.address,
            )
        )


@router.post(
    "/register/customer",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer account",
)
def register_customer(payload: CustomerRegister, db: Session = Depends(get_db)):
    """Register a new customer, hash password, and return JWT token."""
    return register(
        RegisterRequest(
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            password=payload.password,
            role="customer",
            address=payload.address,
            city=payload.city,
            latitude=payload.latitude,
            longitude=payload.longitude,
        ),
        db=db,
    )


@router.post(
    "/register/worker",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new service worker account",
)
def register_worker(payload: WorkerRegister, db: Session = Depends(get_db)):
    """Register a new gig worker, attach skills, and return JWT token."""
    return register(
        RegisterRequest(
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            password=payload.password,
            role="worker",
            experience_years=payload.experience_years,
            hourly_rate=payload.hourly_rate,
            address=payload.address,
            city=payload.city,
            latitude=payload.latitude,
            longitude=payload.longitude,
            skill_ids=payload.skill_ids,
        ),
        db=db,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login (Unified Customer & Worker Authentication)",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate customer or worker by email and password."""
    email_clean = payload.email.strip().lower()

    if payload.role == "worker":
        worker = db.query(WorkerData).filter(func.lower(WorkerData.email) == email_clean).first()
        if worker and verify_password(payload.password, worker.password_hash or ""):
            token = create_access_token(data={"sub": str(worker.worker_id), "role": "worker", "email": worker.email})
            return TokenResponse(
                access_token=token,
                user_type="worker",
                user=UserProfile(
                    id=worker.worker_id, name=worker.name, email=worker.email, phone=worker.phone,
                    role="worker", city=worker.city, address=worker.address
                )
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker email or password.")

    if payload.role == "customer":
        customer = db.query(CustomerData).filter(func.lower(CustomerData.email) == email_clean).first()
        if customer and verify_password(payload.password, customer.password_hash or ""):
            token = create_access_token(data={"sub": str(customer.customer_id), "role": "customer", "email": customer.email})
            return TokenResponse(
                access_token=token,
                user_type="customer",
                user=UserProfile(
                    id=customer.customer_id, name=customer.name, email=customer.email, phone=customer.phone,
                    role="customer", city=customer.city, address=customer.address
                )
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid customer email or password.")

    # Role unspecified — search customer first, then worker
    customer = db.query(CustomerData).filter(func.lower(CustomerData.email) == email_clean).first()
    if customer and verify_password(payload.password, customer.password_hash or ""):
        token = create_access_token(data={"sub": str(customer.customer_id), "role": "customer", "email": customer.email})
        return TokenResponse(
            access_token=token,
            user_type="customer",
            user=UserProfile(
                id=customer.customer_id, name=customer.name, email=customer.email, phone=customer.phone,
                role="customer", city=customer.city, address=customer.address
            )
        )

    worker = db.query(WorkerData).filter(func.lower(WorkerData.email) == email_clean).first()
    if worker and verify_password(payload.password, worker.password_hash or ""):
        token = create_access_token(data={"sub": str(worker.worker_id), "role": "worker", "email": worker.email})
        return TokenResponse(
            access_token=token,
            user_type="worker",
            user=UserProfile(
                id=worker.worker_id, name=worker.name, email=worker.email, phone=worker.phone,
                role="worker", city=worker.city, address=worker.address
            )
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password."
    )


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get current authenticated user profile",
)
def get_me(current_user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return profile data of current JWT bearer."""
    if current_user.role == "customer":
        cust = db.get(CustomerData, current_user.id)
        if not cust:
            raise HTTPException(status_code=404, detail="Customer not found")
        return UserProfile(
            id=cust.customer_id, name=cust.name, email=cust.email, phone=cust.phone,
            role="customer", city=cust.city, address=cust.address
        )
    else:
        w = db.get(WorkerData, current_user.id)
        if not w:
            raise HTTPException(status_code=404, detail="Worker not found")
        return UserProfile(
            id=w.worker_id, name=w.name, email=w.email, phone=w.phone,
            role="worker", city=w.city, address=w.address
        )
