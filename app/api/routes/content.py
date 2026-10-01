from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, owner_or_admin, require_roles
from app.db.session import get_db
from app.models import Announcement, Deadline, Event, Role, User
from app.schemas.common import Message
from app.schemas.content import (AnnouncementIn, AnnouncementOut, AnnouncementUpdate, DeadlineIn, DeadlineOut,
                                 DeadlineUpdate, EventIn, EventOut, EventUpdate)

prof = require_roles(Role.professor)


def _get(db: Session, model, id_: int):
    obj = db.get(model, id_)
    if not obj:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


def _crud(prefix: str, tag: str, model, In, Update, Out, order):
    r = APIRouter(prefix=prefix, tags=[tag])

    @r.get("", response_model=list[Out])
    def list_(skip: int = 0, limit: int = Query(50, le=200), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return db.scalars(select(model).order_by(order(model)).offset(skip).limit(limit)).all()

    @r.post("", response_model=Out, status_code=201)
    def create(body: In, user: User = Depends(prof), db: Session = Depends(get_db)):
        obj = model(**body.model_dump(), user_id=user.id)
        db.add(obj)
        db.commit()
        return obj

    @r.get("/{id_}", response_model=Out)
    def read(id_: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return _get(db, model, id_)

    @r.patch("/{id_}", response_model=Out)
    def update(id_: int, body: Update, user: User = Depends(prof), db: Session = Depends(get_db)):
        obj = _get(db, model, id_)
        owner_or_admin(user, obj.user_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        db.commit()
        return obj

    @r.delete("/{id_}", response_model=Message)
    def delete(id_: int, user: User = Depends(prof), db: Session = Depends(get_db)):
        obj = _get(db, model, id_)
        owner_or_admin(user, obj.user_id)
        db.delete(obj)
        db.commit()
        return Message(detail=f"{model.__name__} deleted")

    return r


announcements = _crud("/announcements", "Announcements", Announcement, AnnouncementIn, AnnouncementUpdate, AnnouncementOut, lambda m: m.created_at.desc())
deadlines = _crud("/deadlines", "Deadlines", Deadline, DeadlineIn, DeadlineUpdate, DeadlineOut, lambda m: m.deadline.asc())
events = _crud("/events", "Events", Event, EventIn, EventUpdate, EventOut, lambda m: m.event_date.desc())
