import re
from datetime import datetime
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.functions import current_user

from backend.app.core.security import require_role, get_current_active_user
from backend.app.models.database import get_db, User, ContactLead, Project, BlogPost, AuditLog, ServiceRequest
from backend.app.schemas import UserOut, UserStatusUpdate, UserUpdateSchema, \
    ServiceRequestOut, ServiceRequestUpdate, ContactLeadCreate, \
    ServiceRequestsPagination, BlogPostCreate  # Asigură-te că importi UserStatusUpdate
from backend.app.schemas import ContactLeadOut, ProjectOut
from backend.app.utils.storage import upload_image_to_bucket

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
    event_data: dict,
    db: Session = Depends(get_db)
):
    try:
        from datetime import datetime
        # Combinăm data și ora
        combined_str = f"{event_data['date']} {event_data['startTime']}"
        preferred_dt = datetime.strptime(combined_str, "%Y-%m-%d %H:%M")

        new_event = ServiceRequest(
            user_id=None,  # Fiind manual, nu avem user_id (de aici era eroarea 500)
            type=event_data.get("type", "Intervenție Manuală"),
            preferred_date=preferred_dt,
            preferred_time=event_data.get("startTime"),
            location=event_data.get("location"),
            phone=event_data.get("phone"),
            description=f"CLIENT: {event_data.get('title')} | {event_data.get('description')}",
            status="accepted",  # O punem direct acceptată să apară în calendar
            created_at=datetime.utcnow()
        )

        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return {"message": "Succes", "id": str(new_event.id)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Eroare baza de date: {str(e)}")


@router.post("/projects", response_model=ProjectOut, dependencies=[admin_dependency])
async def create_project(
        title: str = Form(...),
        description: str = Form(None),
        location: str = Form(...),
        category: str = Form(...),
        capacity_kw: float = Form(...),
        panels_count: int = Form(None),
        investment_value: float = Form(None),
        status: str = Form("completed"),
        is_featured: bool = Form(False),
        image_url: str = Form(...),  # Primești direct URL-ul ca text
        db: Session = Depends(get_db)
):
    try:
        # Nu mai facem upload, folosim direct image_url primit din Form
        new_project = Project(
            title=title,
            description=description,
            location=location,
            category=category,
            capacity_kw=capacity_kw,
            panels_count=panels_count,
            investment_value=investment_value,
            status=status,
            is_featured=is_featured,
            image_url=image_url
        )

        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return new_project

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Eroare la crearea proiectului: {str(e)}"
        )

# Funcție utilitară pentru slug (dacă nu o ai deja importată)
def generate_slug(title: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


@router.post("/blog", dependencies=[admin_dependency])
async def create_blog_post(
        post_data: BlogPostCreate, # Primește tot obiectul JSON odata
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    try:
        # Extragem datele din obiectul post_data
        published_bool = post_data.is_published.lower() == "true"
        tags_list = [t.strip() for t in post_data.tags.split(",")] if post_data.tags else []

        new_post = BlogPost(
            title=post_data.title,
            slug=generate_slug(post_data.title),
            content=post_data.content,
            excerpt=post_data.excerpt,
            category=post_data.category,
            tags=tags_list,
            featured_image=post_data.featured_image, # Acesta este link-ul string
            is_published=published_bool,
            published_at=datetime.utcnow() if published_bool else None,
            author_id=current_user.id
        )

        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        return new_post

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/blog/{post_id}", dependencies=[admin_dependency])
async def delete_blog_post(
        post_id: UUID,
        db: Session = Depends(get_db)
):
    """
    Șterge definitiv un articol de blog din baza de date.
    """
    # 1. Căutăm articolul
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()

    # 2. Dacă nu există, dăm eroare 404
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Articolul de blog nu a fost găsit."
        )

    try:
        # 3. Ștergem articolul
        db.delete(post)
        db.commit()
        return {"message": "Articolul a fost șters cu succes."}

    except Exception as e:
        db.rollback()
        print(f"Eroare la ștergere blog: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Eroare internă la ștergere: {str(e)}"
        )


@router.patch("/projects/{project_id}", response_model=ProjectOut, dependencies=[admin_dependency])
async def update_project(
        project_id: UUID,
        project_data: dict,  # Primim un dicționar pentru a permite update parțial
        db: Session = Depends(get_db)
):
    """
    Actualizează detaliile unui proiect existent.
    """
    # 1. Căutăm proiectul în bază
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Proiectul nu a fost găsit."
        )

    # 2. Mapăm și actualizăm câmpurile trimise din frontend
    # Folosim setattr pentru a actualiza dinamic doar ce a fost trimis
    for key, value in project_data.items():
        if hasattr(project, key):
            setattr(project, key, value)

    try:
        db.commit()
        db.refresh(project)
        return project
    except Exception as e:
        db.rollback()
        print(f"Eroare la update proiect: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Eroare la salvarea modificărilor: {str(e)}"
        )
@router.patch("/blog/{post_id}", dependencies=[admin_dependency])
async def update_blog_post(
    post_id: UUID,
    post_data: dict,
    db: Session = Depends(get_db)
):
    post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Articolul nu a fost găsit.")

    for key, value in post_data.items():
        if hasattr(post, key):
            if key == "is_published" and isinstance(value, str):
                value = value.lower() == "true"
            setattr(post, key, value)

    db.commit()
    db.refresh(post)
    return post