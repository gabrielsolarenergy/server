from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.security import require_role
from backend.app.models.database import get_db, User, ContactLead, Project, BlogPost, AuditLog
from backend.app.schemas import UserOut, ContactLeadOut, ProjectOut

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# Verificăm ca toate rutele de aici să fie accesibile DOAR administratorilor
admin_dependency = Depends(require_role(["admin"]))


# --- GESTIONARE UTILIZATORI ---
@router.get("/users", response_model=List[UserOut], dependencies=[admin_dependency])
async def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


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
@router.get("/leads", response_model=List[ContactLeadOut], dependencies=[admin_dependency])
async def get_all_leads(db: Session = Depends(get_db)):
    return db.query(ContactLead).order_by(ContactLead.created_at.desc()).all()


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