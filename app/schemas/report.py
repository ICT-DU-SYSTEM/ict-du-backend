from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.report import ArchiveCategory, ReportStage, ReportStatus
from app.schemas.common import ORM


class ReportOut(ORM):
    id: int
    title: str
    status: ReportStatus
    stage: ReportStage
    remarks: str | None
    drive_url: str | None
    user_id: int
    created_at: datetime
    updated_at: datetime


class SecretaryReview(BaseModel):
    decision: Literal["forward", "reject"]
    remarks: str | None = None


class ProfessorReview(BaseModel):
    decision: Literal["approve", "reject"]
    remarks: str | None = None


class ArchiveOut(ORM):
    id: int
    name: str
    category: ArchiveCategory
    drive_url: str | None
    uploaded_by: int
    created_at: datetime
