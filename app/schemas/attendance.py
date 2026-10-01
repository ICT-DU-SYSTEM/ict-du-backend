from datetime import datetime

from pydantic import BaseModel, Field

from app.models.attendance import AttendanceStatus
from app.schemas.common import ORM


class GPSIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, description="Accuracy reported by the device")


class GPSOut(BaseModel):
    camera_enabled: bool
    distance_m: float
    attendance_token: str | None = None
    expires_in: int | None = None


class AttendanceOut(ORM):
    id: int
    user_id: int
    check_in_time: datetime | None
    check_out_time: datetime | None
    latitude: float | None
    longitude: float | None
    distance_from_campus: float | None
    face_confidence: float | None
    attendance_status: AttendanceStatus
    reject_reason: str | None
    created_at: datetime
