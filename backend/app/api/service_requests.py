from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.core.security import get_current_user
from backend.app.models.database import get_db, ServiceRequest
from backend.app.schemas import ServiceRequestOut, ServiceRequestCreate

router = APIRouter(prefix="", tags=["Requests"])


@router.post("/", response_model=ServiceRequestOut)
def create_request(
        request_data: ServiceRequestCreate,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    new_request = ServiceRequest(
        **request_data.dict(),
        user_id=current_user.id
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


@router.get("/my-requests", response_model=List[ServiceRequestOut])
def get_my_requests(
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    return db.query(ServiceRequest).filter(ServiceRequest.user_id == current_user.id).all()


@router.post("/{request_id}/accept-reschedule")
def accept_reschedule(
        request_id: str,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    req = db.query(ServiceRequest).filter(
        ServiceRequest.id == request_id,
        ServiceRequest.user_id == current_user.id
    ).first()

    if not req or not req.new_proposed_date:
        raise HTTPException(status_code=404, detail="No reschedule date found")

    req.preferred_date = req.new_proposed_date
    req.new_proposed_date = None
    req.status = "accepted"
    db.commit()
    return {"message": "Date updated successfully"}