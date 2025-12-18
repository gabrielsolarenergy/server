from typing import List
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
async def get_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


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
async def submit_contact(
        data: ContactLeadCreate,
        bg_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    new_lead = ContactLead(**data.dict())
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    bg_tasks.add_task(
        send_email,
        to_email=settings.SMTP_USER,
        subject="🚀 Lead Nou - Gabriel Solar",
        template_name="contact_notification",
        context=data.dict()
    )

    return {"message": "Solicitarea a fost primită. Echipa Gabriel Solar te va contacta în cel mai scurt timp!"}