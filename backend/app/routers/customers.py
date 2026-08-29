"""
routers/customers.py — Customer Management Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CustomerData
from app.schemas import CustomerCreate, CustomerUpdate, CustomerResponse
from app.core.auth import get_current_user, get_optional_current_user, AuthUser

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer",
)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """Create a new customer account."""
    existing = db.query(CustomerData).filter(
        (CustomerData.email == payload.email.lower()) | (CustomerData.phone == payload.phone)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this email or phone already exists."
        )

    new_customer = CustomerData(
        name=payload.name,
        phone=payload.phone,
        email=payload.email.lower(),
        address=payload.address,
        city=payload.city or "Jabalpur",
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return new_customer


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer profile by ID",
)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """Retrieve customer profile by ID."""
    customer = db.get(CustomerData, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with id {customer_id} not found.",
        )
    return customer


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer profile (Protected)",
)
@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Partially update customer profile (Protected)",
)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Update customer profile.
    If authenticated, enforces authorization guard preventing modifying other users' profiles.
    """
    if current_user and current_user.role == "customer" and current_user.id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update another customer's profile."
        )

    customer = db.get(CustomerData, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with id {customer_id} not found."
        )

    if payload.name is not None:
        customer.name = payload.name
    if payload.phone is not None:
        customer.phone = payload.phone
    if payload.address is not None:
        customer.address = payload.address
    if payload.city is not None:
        customer.city = payload.city
    if payload.latitude is not None:
        customer.latitude = payload.latitude
    if payload.longitude is not None:
        customer.longitude = payload.longitude

    db.commit()
    db.refresh(customer)
    return customer
