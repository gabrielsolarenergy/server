import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "GABRIEL SOLAR ENERGY"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Email (SMTP)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAILS_FROM_EMAIL: str = os.getenv("EMAILS_FROM_EMAIL", "noreply@gabriel-solar.ro")
    EMAILS_FROM_NAME: str = "Gabriel Solar Energy"

    # Frontend URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8081")

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Redis (for caching and rate limiting)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_FOLDER: str = "uploads"

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()

