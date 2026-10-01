from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import create_token, hash_password, verify_password
from app.db.session import get_db
from app.models import Role, User
from app.schemas.user import Token, UserCreate, UserOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Constant-cost dummy hash so unknown emails take as long as wrong passwords (no user enumeration by timing)
_DUMMY = hash_password("not-a-real-password")


@router.post("/register", response_model=UserOut, status_code=201, summary="Public self-registration (students only)")
@limiter.limit("10/minute")
def register(request: Request, body: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    user = User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password),
                role=Role.student, position=body.position)
    db.add(user)
    db.commit()
    audit(db, user.id, "register", "user", user.id, request=request)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    ok = verify_password(form.password, user.password_hash if user else _DUMMY)
    if not user or not ok:
        audit(db, user.id if user else None, "login_failed", "user", user.id if user else None, request=request)
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    audit(db, user.id, "login", "user", user.id, request=request)
    return Token(access_token=create_token(str(user.id)), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
