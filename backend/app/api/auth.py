import random
import string

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List

from backend.app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    create_email_token, verify_token, get_current_user, generate_2fa_secret,
    generate_2fa_qr, verify_2fa_code, generate_verification_code, decode_email_token
)
from backend.app.core.email import send_email
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_dependency
from backend.app.models.database import get_db, User, UserSession, AuditLog
from backend.app.schemas import (
    UserCreate, UserLogin, TokenResponse, UserOut,
    PasswordReset, UserOutWith2FA, EmailVerification
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- 1. ÎNREGISTRARE ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()

    if existing_user:
        if not existing_user.is_verified:
            token = create_email_token(existing_user.email, "verify")
            verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
            bg_tasks.add_task(send_email, to_email=existing_user.email, subject="Activează Contul Gabriel Solar",
                              template_name="verify_email",
                              context={"first_name": existing_user.first_name, "verify_link": verify_link})
            return {"message": "Cont existent dar neactivat. Un nou link a fost trimis."}
        raise HTTPException(status_code=400, detail="Email deja înregistrat.")

    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone_number=user_data.phone_number,
        location=user_data.location,
        is_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_email_token(new_user.email, "verify")
    verify_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"

    bg_tasks.add_task(send_email, to_email=new_user.email, subject="Bun venit! Confirmă email-ul",
                      template_name="verify_email",
                      context={"first_name": new_user.first_name, "verify_link": verify_link})

    return {"message": "Cont creat. Verifică email-ul pentru activare."}


@router.get("/verify-email")  # Schimbat din POST in GET pentru a fi accesat direct din browser
async def verify_email(token: str, db: Session = Depends(get_db)):
    email = decode_email_token(token, "verify")
    if not email:
        raise HTTPException(status_code=400, detail="Link invalid sau expirat.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizator negăsit.")

    user.is_verified = True
    db.commit()
    return {"success": True, "message": "Cont activat! Te poți loga."}

# --- 2. LOGIN & SESIUNI ---
@router.post("/login", response_model=TokenResponse)
async def login(
        request: Request,
        login_data: UserLogin,
        db: Session = Depends(get_db)
):
    # 1. Căutare utilizator
    user = db.query(User).filter(User.email == login_data.email).first()

    # 2. Verificare credențiale (Protecție timing attacks)
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email sau parolă incorectă."
        )

    # 3. Blocare cont neverificat (Triggers React Redirect)
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contul nu este verificat. Verifică email-ul."
        )

    # 4. Verificare 2FA (dacă este activat)
    if user.two_factor_enabled:
        if not login_data.totp_code:
            # Returnăm un răspuns parțial care indică necesitatea 2FA
            return {
                "access_token": "pending_2fa",
                "refresh_token": "pending_2fa",
                "user": None,  # Nu trimitem datele userului până nu e validat 2FA
                "requires_2fa": True
            }
        if not verify_2fa_code(user.two_factor_secret, login_data.totp_code):
            raise HTTPException(status_code=401, detail="Cod 2FA invalid.")

    # 5. Generare Token-uri (folosim ID-ul ca subiect)
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # 6. Gestionare Sesiuni
    now = datetime.now(timezone.utc)
    new_session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=request.client.host,
        device_info=request.headers.get("user-agent", "Unknown"),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_session)

    # 7. Update Metadata & Audit
    user.last_login = now

    log = AuditLog(
        user_id=user.id,
        action="LOGIN",
        ip_address=request.client.host,
        created_at=now
    )
    db.add(log)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Eroare la salvarea sesiunii.")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user
    }


# --- 3. REFRESH TOKEN (Sesiuni Persistente) ---
@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    # Verifică token-ul în baza de date
    db_session = db.query(UserSession).filter(UserSession.refresh_token == refresh_token).first()
    if not db_session or db_session.expires_at < datetime.utcnow():
        if db_session: db.delete(db_session); db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expirat sau invalid.")

    payload = verify_token(refresh_token, "refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token.")

    # Generează un nou access token
    new_access_token = create_access_token(data={"sub": payload["sub"]})
    user = db.query(User).filter(User.id == payload["sub"]).first()

    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,
        "user": user
    }


# --- 4. SECURITATE 2FA (Google Authenticator) ---
@router.post("/2fa/setup")
async def setup_2fa(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA este deja activat.")

    secret = generate_2fa_secret()
    current_user.two_factor_secret = secret
    db.commit()

    qr_code_base64 = generate_2fa_qr(current_user.email, secret)
    return {"qr_code": qr_code_base64, "secret": secret}


@router.post("/2fa/verify-and-enable")
async def verify_and_enable_2fa(code: str, current_user: User = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    if verify_2fa_code(current_user.two_factor_secret, code):
        current_user.two_factor_enabled = True
        db.commit()
        return {"message": "2FA a fost activat cu succes."}
    raise HTTPException(status_code=400, detail="Codul introdus este incorect.")


# --- 5. RECUPERARE PAROLĂ ---
@router.post("/forgot-password")
async def forgot_password(email: str, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if user:
        reset_token = create_email_token(user.email, "reset")
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        bg_tasks.add_task(send_email, to_email=user.email, subject="Resetare Parolă",
                         template_name="reset_password", context={"first_name": user.first_name, "reset_link": reset_link})
    return {"message": "Dacă email-ul există, un link de resetare a fost trimis."}


@router.post("/reset-password-confirm")
async def reset_password_confirm(data: PasswordReset, db: Session = Depends(get_db)):
    payload = verify_token(data.token, "reset")
    if not payload:
        raise HTTPException(status_code=400, detail="Link expirat sau invalid.")

    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizator negăsit.")

    user.hashed_password = hash_password(data.new_password)
    # Revocăm toate sesiunile vechi pentru securitate
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()
    db.commit()

    return {"message": "Parola a fost actualizată. Te poți loga."}


# --- 6. LOGOUT ---
@router.post("/logout")
async def logout(refresh_token: str, db: Session = Depends(get_db)):
    db.query(UserSession).filter(UserSession.refresh_token == refresh_token).delete()
    db.commit()
    return {"message": "Sesiune închisă cu succes."}


@router.post("/logout-all", dependencies=[Depends(get_current_user)])
async def logout_all_devices(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Șterge toate sesiunile utilizatorului (security feature)
    db.query(UserSession).filter(UserSession.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Te-ai delogat de pe toate dispozitivele."}