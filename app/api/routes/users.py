from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Role, User
from app.schemas.common import Message
from app.schemas.user import AdminUserCreate, UserOut, UserUpdate
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["Users"])
staff = require_roles(Role.professor, Role.secretary)
admin_only = require_roles()  # admin is always allowed


@router.get("", response_model=list[UserOut])
def list_users(role: Role | None = None, skip: int = 0, limit: int = Query(50, le=200),
               _: User = Depends(staff), db: Session = Depends(get_db)):
    q = select(User).order_by(User.id).offset(skip).limit(limit)
    if role:
        q = q.where(User.role == role)
    return db.scalars(q).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: AdminUserCreate, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    u = User(name=body.name, email=body.email.lower(), password_hash=hash_password(body.password), role=body.role, position=body.position)
    db.add(u)
    db.commit()
    audit(db, admin.id, "user_create", "user", u.id, f"role={u.role.value}", request)
    return u


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if me.role == Role.student and me.id != user_id:
        raise HTTPException(403, "Insufficient permissions")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, request: Request, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if me.role != Role.admin and me.id != user_id:
        raise HTTPException(403, "Insufficient permissions")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and me.role != Role.admin:
        raise HTTPException(403, "Only admins can change roles")  # blocks privilege escalation
    if "email" in data:
        data["email"] = data["email"].lower()
        if db.scalar(select(User).where(User.email == data["email"], User.id != user_id)):
            raise HTTPException(409, "Email already registered")
    if "password" in data:
        u.password_hash = hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(u, k, v)
    db.commit()
    audit(db, me.id, "user_update", "user", u.id, ",".join(body.model_dump(exclude_unset=True).keys()), request)
    return u


@router.delete("/{user_id}", response_model=Message)
def delete_user(user_id: int, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if admin.id == user_id:
        raise HTTPException(400, "You cannot delete your own account")
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    db.delete(u)
    db.commit()
    audit(db, admin.id, "user_delete", "user", user_id, request=request)
    return Message(detail="User deleted")
