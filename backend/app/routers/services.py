"""
routers/services.py — Service Catalog Management
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models import Service, Skill
from app.schemas import ServiceCreate, ServiceResponse

router = APIRouter(prefix="/services", tags=["Services"])


@router.get(
    "",
    response_model=List[ServiceResponse],
    summary="List all available services",
)
def get_services(
    category: Optional[str] = Query(None, description="Filter by category (e.g. 'Household', 'Appliance')"),
    skill_id: Optional[int] = Query(None, description="Filter by skill ID"),
    db: Session = Depends(get_db),
):
    """Returns the full service catalog with linked skill details."""
    query = db.query(Service).options(joinedload(Service.skill))
    if category:
        query = query.filter(func.lower(Service.category) == category.lower())
    if skill_id:
        query = query.filter(Service.skill_id == skill_id)

    services = query.order_by(Service.service_id).all()
    # Ensure aliases are populated
    results = []
    for s in services:
        results.append(
            ServiceResponse(
                service_id=s.service_id,
                service_name=s.service_name,
                service=s.service_name,
                description=s.description,
                category=s.category,
                base_price=float(s.base_price),
                estimated_duration=s.estimated_duration or 60,
                skill_id=s.skill_id,
                skill=s.skill,
            )
        )
    return results


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Get a specific service by ID",
)
def get_service(service_id: int, db: Session = Depends(get_db)):
    """Retrieve single service details with skill mapping."""
    service = (
        db.query(Service)
        .options(joinedload(Service.skill))
        .filter(Service.service_id == service_id)
        .first()
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with id {service_id} not found.",
        )
    return ServiceResponse(
        service_id=service.service_id,
        service_name=service.service_name,
        service=service.service_name,
        description=service.description,
        category=service.category,
        base_price=float(service.base_price),
        estimated_duration=service.estimated_duration or 60,
        skill_id=service.skill_id,
        skill=service.skill,
    )


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service offering",
)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    """Create a new standardized service catalog item."""
    skill = db.get(Skill, payload.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Referenced skill_id does not exist.")

    service = Service(
        service_name=payload.service_name,
        description=payload.description,
        category=payload.category or "Household",
        base_price=payload.base_price,
        estimated_duration=payload.estimated_duration or 60,
        skill_id=payload.skill_id,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return ServiceResponse(
        service_id=service.service_id,
        service_name=service.service_name,
        service=service.service_name,
        description=service.description,
        category=service.category,
        base_price=float(service.base_price),
        estimated_duration=service.estimated_duration or 60,
        skill_id=service.skill_id,
        skill=skill,
    )
