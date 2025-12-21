import time
import logging
from fastapi import FastAPI, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# Importuri locale
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_dependency
from backend.app.models.database import Base, engine, get_db
from backend.app.api import auth, solar, chat, admin
from backend.app.api import service_requests # Importă fișierul nou creat
# Configurare Logging pentru monitorizarea erorilor în producție
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inițializare Tabele Bază de Date (Notă: În producție se recomandă utilizarea Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sistem Enterprise de Management pentru Gabriel Solar Energy",
    docs_url="/api/docs",  # Documentație Swagger customizată
    redoc_url="/api/redoc"
)

# ============================================
# MIDDLEWARE CONFIGURATION
# ============================================

# 1. CORS: Securitate pentru accesul din Frontend
# În backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081",
                   "gabriel-solar-energy.ro",
                   "http://gabriel-solar-energy.ro",
                   "https://gabriel-solar-energy.ro",
                   "https://sparkling-sunburst-33a9b7.netlify.app"
                   ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    service_requests.router,
    prefix="/api/v1/service-requests"
)
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    # Logare cereri lente (> 2 secunde)
    if process_time > 2.0:
        logger.warning(f"Slow request: {request.url.path} took {process_time:.4f}s")

    return response


# 3. Global Exception Handler: Protecție împotriva scurgerii de date tehnice în caz de eroare
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Error on {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "O eroare internă a apărut. Echipa tehnică a fost notificată."}
    )


# ============================================
# STATIC FILES & UPLOADS
# ============================================

# Servire fișiere statice (imagini proiecte, blog, etc.)
# Asigură-te că directorul 'uploads' există
import os

if not os.path.exists(settings.UPLOAD_FOLDER):
    os.makedirs(settings.UPLOAD_FOLDER)

app.mount("/static", StaticFiles(directory=settings.UPLOAD_FOLDER), name="static")

# ============================================
# ROUTER REGISTRATION
# ============================================

# Toate rutele sunt grupate sub prefixul definit în config (implicit /api/v1)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(solar.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)


# ============================================
# HEALTH CHECK & ROOT
# ============================================

@app.get("/", tags=["Health Check"])
async def root():
    """Verifică dacă API-ul este online."""
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": time.time()
    }


@app.get("/health", tags=["Health Check"])
async def health_check(db: Session = Depends(get_db)):
    """Verifică conexiunea la baza de date."""
    try:
        # Executăm o interogare simplă pentru a valida conexiunea la Postgres
        db.execute("SELECT 1")
        return {"database": "connected", "server": "running"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={"database": "disconnected", "error": "Service Unavailable"}
        )


# ============================================
# EXECUTION LOGIC
# ============================================

if __name__ == "__main__":
    import uvicorn
    # Schimbă "app.main:app" cu "backend.app.main:app"
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )