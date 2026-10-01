from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import Position, Role
from app.schemas.common import ORM


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt ignores >72 bytes
    position: Position | None = None


class AdminUserCreate(UserCreate):
    role: Role = Role.student


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    position: Position | None = None
    role: Role | None = None  # admin only (enforced in route)


class UserOut(ORM):
    id: int
    name: str
    email: EmailStr
    role: Role
    position: Position | None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
