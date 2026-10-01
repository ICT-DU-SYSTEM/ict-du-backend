import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, sa_enum


class ReportStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ReportStage(str, enum.Enum):
    """Where the report is in Student -> Secretary -> Professor -> Archive."""
    pending_secretary = "pending_secretary"
    pending_professor = "pending_professor"
    completed = "completed"


class Report(Base, TimestampMixin):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    file_path: Mapped[str] = mapped_column(String(500))
    drive_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    drive_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ReportStatus] = mapped_column(sa_enum(ReportStatus, "report_status"), default=ReportStatus.pending, index=True)
    stage: Mapped[ReportStage] = mapped_column(sa_enum(ReportStage, "report_stage"), default=ReportStage.pending_secretary, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    author = relationship("User")


class ArchiveCategory(str, enum.Enum):
    report = "report"
    event = "event"
    announcement = "announcement"
    competition = "competition"


class Archive(Base):
    __tablename__ = "archives"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[ArchiveCategory] = mapped_column(sa_enum(ArchiveCategory, "archive_category"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    drive_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    drive_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
