import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.security import get_current_user
from backend.app.models.database import get_db, ServiceRequest
from backend.app.schemas import ServiceRequestOut
from backend.app.utils.storage import upload_image_to_bucket

router = APIRouter(prefix="", tags=["Requests"])


@router.post("/", response_model=ServiceRequestOut)
async def create_request(
        # Folosim Form(...) deoarece datele vin la pachet cu fișiere binare
        type: str = Form(...),
        location: str = Form(...),
        phone: str = Form(...),
        preferred_date: str = Form(...),
        preferred_time: str = Form(...),
        description: Optional[str] = Form(None),
        images: List[UploadFile] = File([]),  # Preluăm fișierele din inputul 'images'
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    try:
        # 1. Procesăm și urcăm imaginile în Bucket-ul Railway
        image_urls = []
        for img in images:
            url = await upload_image_to_bucket(img)
            image_urls.append(url)

        # 2. Creăm obiectul pentru baza de date
        # Convertim string-ul de dată primit din frontend în obiect datetime
        date_obj = datetime.fromisoformat(preferred_date.replace('Z', '+00:00'))

        new_request = ServiceRequest(
            id=uuid.uuid4(),
            user_id=current_user.id,
            type=type,
            location=location,
            phone=phone,
            preferred_date=date_obj,
            preferred_time=preferred_time,
            description=description,
            photos=image_urls,  # Lista de URL-uri (stocată ca JSON în DB)
            status="pending"
        )

        db.add(new_request)
        db.commit()
        db.refresh(new_request)
        return new_request

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Eroare la crearea cererii: {str(e)}")


@router.get("/my-requests", response_model=List[ServiceRequestOut])
def get_my_requests(
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    # Sortăm descrescător după data creării pentru a vedea cererile noi primele
    return db.query(ServiceRequest).filter(
        ServiceRequest.user_id == current_user.id
    ).order_by(ServiceRequest.created_at.desc()).all()


@router.post("/{request_id}/accept-reschedule")
def accept_reschedule(
        request_id: str,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    # Convertim string-ul ID în UUID pentru interogare
    try:
        request_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format ID invalid")

    req = db.query(ServiceRequest).filter(
        ServiceRequest.id == request_uuid,
        ServiceRequest.user_id == current_user.id
    ).first()

    if not req or not req.new_proposed_date:
        raise HTTPException(status_code=404, detail="Nu s-a găsit nicio propunere de reprogramare")

    # Clientul acceptă: data propusă devine data preferată
    req.preferred_date = req.new_proposed_date
    req.new_proposed_date = None
    req.status = "accepted"

    db.commit()
    return {"message": "Data a fost actualizată cu succes"}