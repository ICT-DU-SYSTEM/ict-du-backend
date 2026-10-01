from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import day_bounds_utc, local_now
from app.models import (Announcement, Attendance, AttendanceStatus, Deadline, Event, Report, Role, Team, User)
from app.services.attendance import ACCEPTED


def _count(db: Session, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def summary(db: Session) -> dict:
    s, e = day_bounds_utc(local_now().date())
    today = (Attendance.check_in_time >= s, Attendance.check_in_time < e)
    students = _count(db, User, User.role == Role.student)
    attended = db.scalar(select(func.count(func.distinct(Attendance.user_id))).where(Attendance.attendance_status.in_(ACCEPTED), *today)) or 0
    late_rows = db.execute(select(User.id, User.name, Attendance.check_in_time).join(Attendance, Attendance.user_id == User.id)
                           .where(Attendance.attendance_status == AttendanceStatus.late, *today)).all()
    return {
        "totals": {
            "students": students,
            "professors": _count(db, User, User.role == Role.professor),
            "secretaries": _count(db, User, User.role == Role.secretary),
            "events": _count(db, Event),
            "teams": _count(db, Team),
            "reports": _count(db, Report),
            "attendance_today": attended,
            "attendance_rate_percent": round(attended / students * 100, 1) if students else 0.0,
            "late_students": len(late_rows),
        },
        "late_students": [{"user_id": r.id, "name": r.name, "check_in_time": r.check_in_time} for r in late_rows],
        "recent": {
            "announcements": [{"id": a.id, "title": a.title, "created_at": a.created_at}
                              for a in db.scalars(select(Announcement).order_by(Announcement.created_at.desc()).limit(5))],
            "deadlines": [{"id": d.id, "title": d.title, "deadline": d.deadline}
                          for d in db.scalars(select(Deadline).order_by(Deadline.deadline.desc()).limit(5))],
            "events": [{"id": v.id, "title": v.title, "event_date": v.event_date, "type": v.type.value}
                       for v in db.scalars(select(Event).order_by(Event.event_date.desc()).limit(5))],
            "reports": [{"id": r.id, "title": r.title, "status": r.status.value, "stage": r.stage.value}
                        for r in db.scalars(select(Report).order_by(Report.created_at.desc()).limit(5))],
        },
    }
