from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from slugify import slugify

from backend.app.core.config import settings
from backend.app.core.email import send_email
from backend.app.core.security import get_current_active_user, require_role, get_current_user
from backend.app.models.database import Project, BlogPost, ContactLead, get_db, User
from backend.app.schemas import (
    ProjectCreate, ProjectOut,
    BlogPostCreate, BlogPostOut,
    ContactLeadCreate
)

router = APIRouter(prefix="/solar", tags=["Solar Content"])


# --- PROIECTE (Acces Public la Vizualizare) ---
@router.get("/projects", response_model=List[ProjectOut])
async def get_projects(
        category: Optional[str] = Query(None),  # Frontend trimite 'category'
        page: int = Query(1, ge=1),
        size: int = Query(6, ge=1),
        db: Session = Depends(get_db)
):
    query = db.query(Project)

    # 1. Aplicăm filtrul de categorie (dacă este trimis)
    if category and category != "all":
        # Folosim ilike pentru a fi case-insensitive și a ignora mici diferențe
        query = query.filter(Project.category.ilike(f"%{category}%"))

    # 2. Ordonăm după data creării
    query = query.order_by(Project.created_at.desc())

    # 3. Aplicăm paginarea
    skip = (page - 1) * size
    projects = query.offset(skip).limit(size).all()

    return projects

@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proiectul nu a fost găsit")
    return project


# --- BLOG (Filtrare postări publicate) ---
@router.get("/blog", response_model=List[BlogPostOut])
async def get_blog_posts(db: Session = Depends(get_db)):
    return db.query(BlogPost).filter(BlogPost.is_published == True).order_by(BlogPost.created_at.desc()).all()


@router.get("/blog/{slug}", response_model=BlogPostOut)
async def get_blog_post(slug: str, db: Session = Depends(get_db)):
    post = db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.is_published == True).first()
    if not post:
        raise HTTPException(status_code=404, detail="Articolul nu există")

    # Incrementare vizualizări (Performanță asincronă ar fi ideală aici)
    post.views_count += 1
    db.commit()
    return post


# --- LEAD MANAGEMENT (Contact) ---
@router.post("/contact")
async def submit_contact(data: ContactLeadCreate, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    new_lead = ContactLead(**data.dict())
    db.add(new_lead)
    db.commit()

    bg_tasks.add_task(send_email, to_email=settings.SMTP_USER, subject="🚀 Lead Nou - Gabriel Solar",
                      template_name="contact_notification", context=data.dict())
    return {"message": "Solicitarea a fost primită!"}
@router.get("/blog", response_model=List[BlogPostOut]) # Sau un model de paginare dacă preferi
async def get_blog_posts(
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(6, ge=1),
    db: Session = Depends(get_db)
):
    query = db.query(BlogPost).filter(BlogPost.is_published == True)

    # 1. Filtrare după categorie (dacă nu e "all" sau "Toate postările")
    if category and category not in ["all", "Toate postările"]:
        # Folosim ilike pentru a fi siguri că găsim categoria indiferent de litere mari/mici
        query = query.filter(BlogPost.category.ilike(f"%{category}%"))

    # 2. Ordonare (cele mai noi primele)
    query = query.order_by(BlogPost.created_at.desc())

    # 3. Paginare
    skip = (page - 1) * size
    posts = query.offset(skip).limit(size).all()

    return posts