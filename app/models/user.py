import enum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, sa_enum


class Role(str, enum.Enum):
    student = "student"
    professor = "professor"
    secretary = "secretary"
    admin = "admin"


class Position(str, enum.Enum):
    frontend = "Frontend Developer"
    backend = "Backend Developer"
    ai = "AI Engineer"
    devops = "DevOps Engineer"
    qa = "Quality Assurance"
    uiux = "UI/UX Designer"
    business = "Business Manager"


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(sa_enum(Role, "role"), default=Role.student, index=True)
    position: Mapped[Position | None] = mapped_column(sa_enum(Position, "position"), nullable=True)
