import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func

from backend.app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    phone_number = Column(String(20))
    location = Column(String(100))

    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String, nullable=True)

    last_login = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # RELATIONSHIPS - CORECTATE
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

    # Aici îi spunem clar că relația standard "Proprietar Lead" folosește coloana user_id
    contact_leads = relationship(
        "ContactLead",
        back_populates="user",
        foreign_keys="ContactLead.user_id",
        cascade="all, delete-orphan"
    )

    blog_posts = relationship("BlogPost", back_populates="author")
    chat_messages = relationship("ChatMessage", back_populates="user")

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    refresh_token = Column(String, unique=True, index=True)
    device_info = Column(String(255))
    ip_address = Column(String(45))
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class ContactLead(Base):
    __tablename__ = "contact_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    full_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    phone = Column(String(20))
    property_type = Column(String(50))
    interest = Column(String(100))
    message = Column(Text)

    status = Column(String(20), default="new")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # RELATIONSHIPS - CORECTATE
    # Relația către cel care a creat lead-ul
    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="contact_leads"
    )

    # Relația către adminul asignat (nu are back_populates pentru a evita conflictele)
    assigned_user = relationship(
        "User",
        foreign_keys=[assigned_to]
    )

    # Relația pentru adminul/agentul asignat să proceseze lead-ul
    assigned_user = relationship(
        "User",
        foreign_keys=[assigned_to]
    )

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    location = Column(String(200))
    category = Column(String(50))  # residential, commercial, industrial

    capacity_kw = Column(Float)
    panels_count = Column(Integer)
    investment_value = Column(Float)

    status = Column(String(20), default="completed")  # planning, in_progress, completed
    completion_date = Column(DateTime)

    image_url = Column(String(500))
    images = Column(JSON)  # Multiple images

    is_featured = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    slug = Column(String(300), unique=True, index=True)
    content = Column(Text, nullable=False)
    excerpt = Column(Text)

    category = Column(String(50))
    tags = Column(JSON)

    featured_image = Column(String(500))

    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime)

    views_count = Column(Integer, default=0)

    seo_title = Column(String(255))
    seo_description = Column(String(500))
    seo_keywords = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", back_populates="blog_posts")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(String(100), index=True)  # Format: user_{user_id}
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    message = Column(Text, nullable=False)
    is_admin = Column(Boolean, default=False)

    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_messages")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(String(100))
    details = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


# Create all tables
Base.metadata.create_all(bind=engine)
