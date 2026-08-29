"""
routers/availability.py — Worker Slot & Real-time Availability Management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Availability, WorkerData
from app.schemas import AvailabilityCreate, AvailabilityUpdate, AvailabilityResponse
from app.core.auth import get_optional_current_user, AuthUser

router = APIRouter(prefix="/availability", tags=["Availability"])


@router.get(
    "/{worker_id}",
    response_model=List[AvailabilityResponse],
    summary="Get worker availability slots and status",
)
def get_worker_availability(worker_id: int, db: Session = Depends(get_db)):
    """Retrieve all availability records and slots for a worker."""
    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found.")

    slots = db.query(Availability).filter(Availability.worker_id == worker_id).all()
    if not slots:
        # Return default active status slot if none exist
        return [
            AvailabilityResponse(
                availability_id=None,
                worker_id=worker_id,
                date=None,
                start_time=None,
                end_time=None,
                is_available=True,
            )
        ]
    return slots


@router.post(
    "",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update worker availability slot",
)
def create_availability_slot(
    payload: AvailabilityCreate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Add a calendar availability slot for a worker."""
    target_worker_id = payload.worker_id
    if not target_worker_id:
        if current_user and current_user.role == "worker":
            target_worker_id = current_user.id
        else:
            raise HTTPException(status_code=400, detail="worker_id is required.")

    if current_user and current_user.role == "worker" and current_user.id != target_worker_id:
        raise HTTPException(status_code=403, detail="Cannot create availability slot for another worker.")

    worker = db.get(WorkerData, target_worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {target_worker_id} not found.")

    slot = Availability(
        worker_id=target_worker_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_available=payload.is_available,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@router.patch(
    "/{worker_id}/toggle",
    response_model=AvailabilityResponse,
    summary="Toggle worker availability status",
)
def toggle_availability(
    worker_id: int,
    payload: AvailabilityUpdate,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Quickly toggle worker's real-time availability."""
    if current_user and current_user.role == "worker" and current_user.id != worker_id:
        raise HTTPException(status_code=403, detail="Cannot toggle availability for another worker.")

    worker = db.get(WorkerData, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found.")

    avail = db.query(Availability).filter(Availability.worker_id == worker_id).first()
    if not avail:
        avail = Availability(worker_id=worker_id, is_available=payload.is_available)
        db.add(avail)
    else:
        avail.is_available = payload.is_available
        avail.updated_at = func.now()

    db.commit()
    db.refresh(avail)
    return avail


@router.delete(
    "/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an availability slot",
)
def delete_availability_slot(
    availability_id: int,
    current_user: Optional[AuthUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Delete a specific availability slot."""
    slot = db.get(Availability, availability_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Availability slot not found.")

    if current_user and current_user.role == "worker" and current_user.id != slot.worker_id:
        raise HTTPException(status_code=403, detail="Cannot delete another worker's slot.")

    db.delete(slot)
    db.commit()
    return None
