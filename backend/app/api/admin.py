from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.security import require_role
from backend.app.models.database import get_db, User, ContactLead, Project, BlogPost, AuditLog
from backend.app.schemas import UserOut, UserStatusUpdate  # Asigură-te că importi UserStatusUpdate
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

@router.patch("/leads/{lead_id}/status", dependencies=[admin_dependency])
async def update_lead_status(lead_id: UUID, status: str, db: Session = Depends(get_db)):
    lead = db.query(ContactLead).filter(ContactLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead negăsit")

    lead.status = status
    db.commit()
    return {"message": "Status lead actualizat"}


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