from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import re

# --- USER SCHEMAS ---

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone_number: Optional[str] = None
    location: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=100)

    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Parola trebuie să conțină cel puțin o literă mare.')
        if not re.search(r'[a-z]', v):
            raise ValueError('Parola trebuie să conțină cel puțin o literă mică.')
        if not re.search(r'\d', v):
            raise ValueError('Parola trebuie să conțină cel puțin o cifră.')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None

class UserOut(UserBase):
    id: UUID
    role: str
    is_verified: bool
    two_factor_enabled: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# SCHEMA LIPSĂ: Folosită pentru răspunsul de login când 2FA este activ
class UserOutWith2FA(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    requires_2fa: bool = False

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    requires_2fa: Optional[bool] = False

class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

# --- CONTACT & LEAD SCHEMAS ---

class ContactLeadCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    property_type: str
    interest: str
    message: Optional[str] = None

class ContactLeadOut(ContactLeadCreate):
    id: UUID
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- PROJECT SCHEMAS ---

class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    category: str
    capacity_kw: Optional[float] = None
    panels_count: Optional[int] = None
    investment_value: Optional[float] = None
    status: str = "completed"
    image_url: Optional[str] = None

class ProjectOut(ProjectCreate):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# --- BLOG SCHEMAS ---

class BlogPostCreate(BaseModel):
    title: str
    content: str
    category: str
    tags: Optional[List[str]] = []
    featured_image: Optional[str] = None
    is_published: bool = False

class BlogPostOut(BlogPostCreate):
    id: UUID
    slug: str
    author_id: UUID
    views_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class EmailVerification(BaseModel):
    email: EmailStr
    code: str