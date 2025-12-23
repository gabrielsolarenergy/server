from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from backend.app.core.security import require_role
from backend.app.models.database import get_db, User, ContactLead, Project, BlogPost, AuditLog, ServiceRequest
from backend.app.schemas import UserOut, UserStatusUpdate, UserUpdateSchema, \
    ServiceRequestOut, ServiceRequestUpdate, ContactLeadCreate, \
    ServiceRequestsPagination  # Asigură-te că importi UserStatusUpdate
from backend.app.schemas import ContactLeadOut, ProjectOut

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# Verificăm ca toate rutele de aici să fie accesibile DOAR administratorilor
admin_dependency = Depends(require_role(["admin"]))


# --- GESTIONARE UTILIZATORI ---

@router.get("/users", response_model=List[UserOut], dependencies=[admin_dependency])
async def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.patch("/users/{user_id}/status", dependencies=[admin_dependency])
async def update_user_status(
        user_id: UUID,
        status_data: UserStatusUpdate,
        db: Session = Depends(get_db)
):
    """
    Endpoint protejat: Permite doar administratorilor să schimbe statusul de verificare al unui user.
    """
    # 1. Căutăm utilizatorul în baza de date
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit.")

    # 2. Actualizăm câmpul conform datelor trimise din Frontend
    user.is_verified = status_data.is_verified

    # 3. Salvăm modificările în Postgres
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Eroare la actualizarea bazei de date.")

    return {
        "message": f"Statusul utilizatorului {user.email} a fost actualizat cu succes.",
        "user_id": user.id,
        "is_verified": user.is_verified
    }


@router.patch("/users/{user_id}/role", dependencies=[admin_dependency])
async def change_user_role(user_id: UUID, new_role: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizator negăsit")

    if new_role not in ["user", "admin", "editor", "sales"]:
        raise HTTPException(status_code=400, detail="Rol invalid")

    user.role = new_role
    db.commit()
    return {"message": f"Rolul utilizatorului {user.email} a fost schimbat în {new_role}"}


# --- MANAGEMENT LEADS (CRM) ---
@router.get("/leads", dependencies=[admin_dependency])
async def get_all_leads(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(6, ge=1, le=100),
    search: str = Query(None),
    status: str = Query(None),
    property_type: str = Query(None)
):
    query = db.query(ContactLead)

    # Aplicăm filtrul de căutare (Nume, Email sau Telefon)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                ContactLead.full_name.ilike(search_filter),
                ContactLead.email.ilike(search_filter),
                ContactLead.phone.ilike(search_filter)
            )
        )

    # Aplicăm filtrul de status
    if status and status != "all":
        query = query.filter(ContactLead.status == status)

    # Aplicăm filtrul de tip proprietate
    if property_type and property_type != "all":
        query = query.filter(ContactLead.property_type == property_type)

    # Calculăm totalul după filtrare, dar înainte de paginare
    total_items = query.count()
    total_pages = (total_items + size - 1) // size if total_items > 0 else 1

    # Paginare
    leads = query.order_by(ContactLead.created_at.desc())\
                 .offset((page - 1) * size)\
                 .limit(size)\
                 .all()

    return {
        "items": leads,
        "total_pages": total_pages,
        "current_page": page,
        "total_items": total_items
    }


@router.delete("/leads/{lead_id}", dependencies=[admin_dependency])
async def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(ContactLead).filter(ContactLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead-ul nu a fost găsit")

    db.delete(lead)
    db.commit()
    return {"message": "Lead șters cu succes"}


@router.patch("/users/{user_id}", dependencies=[admin_dependency])
async def update_user(
        user_id: str,
        user_data: UserUpdateSchema,
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")

    # Update fields
    update_dict = user_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(user, key, value)

    db.commit()
    return {"message": "Utilizator actualizat cu succes"}

@router.patch("/leads/{lead_id}/status", dependencies=[admin_dependency])
async def update_lead_status(lead_id: UUID, status: str, db: Session = Depends(get_db)):
    lead = db.query(ContactLead).filter(ContactLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead negăsit")

    lead.status = status
    db.commit()
    return {"message": "Status lead actualizat"}

# --- ADAUGĂ ACEASTA ÎN BACKEND (fișierul cu rutele de admin) ---

@router.post("/leads", response_model=ContactLeadOut, dependencies=[admin_dependency])
async def create_lead(
        lead_data: ContactLeadCreate,
        db: Session = Depends(get_db)
):
    """
    Creează un lead nou manual din panoul de admin.
    """
    new_lead = ContactLead(
        full_name=lead_data.full_name,
        email=lead_data.email,
        phone=lead_data.phone,
        property_type=lead_data.property_type,
        interest=lead_data.interest,
        message=lead_data.message,
        status="nou",  # Default status
        source="Admin Panel"
    )

    try:
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        return new_lead
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Eroare la salvarea lead-ului în baza de date.")

@router.patch("/leads/{lead_id}", response_model=ContactLeadOut, dependencies=[admin_dependency])
async def update_lead_details(
    lead_id: UUID,
    lead_data: dict, # Folosim dict pentru a permite update parțial (nume, email, etc.)
    db: Session = Depends(get_db)
):
    """
    Actualizează detaliile generale ale unui lead.
    """
    lead = db.query(ContactLead).filter(ContactLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead-ul nu a fost găsit.")

    # Actualizăm câmpurile care există în baza de date și sunt trimise din front-end
    for key, value in lead_data.items():
        if hasattr(lead, key):
            setattr(lead, key, value)

    try:
        db.commit()
        db.refresh(lead)
        return lead
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Eroare la actualizarea lead-ului.")

# --- AUDIT LOGS (Monitorizare activitate) ---
@router.get("/audit-logs", dependencies=[admin_dependency])
async def get_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()


# --- DELETE OPERATIONS (High Security) ---
@router.delete("/projects/{project_id}", dependencies=[admin_dependency])
async def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404)
    db.delete(project)
    db.commit()
    return {"message": "Proiect șters definitiv"}


@router.get("/all", response_model=ServiceRequestsPagination, dependencies=[admin_dependency])
def get_all_requests_admin(
        service_type: str = Query(None),
        status: str = Query(None),
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        db: Session = Depends(get_db)
):
    # 1. Query-ul de bază cu JOIN pentru user
    query = db.query(ServiceRequest).options(joinedload(ServiceRequest.user))

    # 2. Aplicăm filtrele
    if service_type and service_type != "all":
        query = query.filter(ServiceRequest.type == service_type)

    if status and status != "all":
        query = query.filter(ServiceRequest.status == status)

    # 3. Calculăm totalul înainte de paginare
    total_count = query.count()
    total_pages = (total_count + size - 1) // size if total_count > 0 else 1

    # 4. Aplicăm ordonarea și limitele de paginare
    # offset = numărul de elemente peste care sărim
    # limit = câte elemente luăm
    items = query.order_by(ServiceRequest.created_at.desc()) \
        .offset((page - 1) * size) \
        .limit(size) \
        .all()

    return {
        "items": items,
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page
    }


# Modifică în backend/app/api/admin.py
@router.patch("/{request_id}/respond", dependencies=[admin_dependency])
def respond_to_request(
        request_id: UUID,  # Schimbă din str în UUID
        data: ServiceRequestUpdate,
        db: Session = Depends(get_db)):
    req = db.query(ServiceRequest).filter(ServiceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Cererea nu a fost găsită")

    # Actualizăm câmpurile trimise (status, admin_response, new_proposed_date)
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(req, key, value)

    try:
        db.commit()
        db.refresh(req)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Eroare la salvarea răspunsului")

    return {"message": "Răspuns înregistrat cu succes", "status": req.status}


# --- CALENDAR EVENTS ---

@router.post("/calendar-events", dependencies=[admin_dependency])
async def create_calendar_event(
        event_data: dict,  # Poți folosi un Schema Pydantic dedicat dacă preferi
        db: Session = Depends(get_db)
):
    """
    Creează o programare manuală direct în tabela ServiceRequests
    pentru a apărea în calendar.
    """
    try:
        # Combinăm data și ora primite din frontend într-un obiect datetime
        # Frontend-ul trimite 'date' (YYYY-MM-DD) și 'startTime' (HH:MM)
        from datetime import datetime
        combined_str = f"{event_data['date']} {event_data['startTime']}"
        preferred_dt = datetime.strptime(combined_str, "%Y-%m-%d %H:%M")

        new_event = ServiceRequest(
            type=event_data.get("type", "Intervenție Manuală"),
            preferred_date=preferred_dt,
            preferred_time=event_data.get("startTime"),
            location=event_data.get("location"),
            phone=event_data.get("phone"),
            description=event_data.get("description"),
            status="accepted",  # O marcăm direct ca acceptată pentru a apărea în calendar
            admin_response="Programare manuală creată de administrator.",
            # full_name poate fi stocat în description sau poți adăuga coloana în model
        )

        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return {"message": "Eveniment creat cu succes", "id": new_event.id}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Eroare la salvarea în baza de date: {str(e)}"
        )