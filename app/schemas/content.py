from datetime import datetime

from pydantic import BaseModel, Field

from app.models.content import EventType
from app.schemas.common import ORM


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)


class AnnouncementOut(ORM, AnnouncementIn):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class DeadlineIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    deadline: datetime


class DeadlineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    deadline: datetime | None = None


class DeadlineOut(ORM, DeadlineIn):
    id: int
    user_id: int
    created_at: datetime


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    event_date: datetime
    location: str | None = Field(default=None, max_length=255)
    type: EventType


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    event_date: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    type: EventType | None = None


class EventOut(ORM, EventIn):
    id: int
    user_id: int
    created_at: datetime
