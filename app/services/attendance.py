from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import day_bounds_utc, local_now, parse_hhmm, utcnow_naive
from app.models import Attendance, AttendanceStatus, Role, User

ACCEPTED = (AttendanceStatus.present, AttendanceStatus.late)


def status_for_now() -> AttendanceStatus:
    """Before LATE_AFTER (08:15) -> present, otherwise late. Uses SERVER time, never client time."""
    return AttendanceStatus.present if local_now().time() < parse_hhmm(settings.LATE_AFTER) else AttendanceStatus.late


def _today_filter():
    s, e = day_bounds_utc(local_now().date())
    return Attendance.check_in_time >= s, Attendance.check_in_time < e


def accepted_today(db: Session, user_id: int) -> Attendance | None:
    a, b = _today_filter()
    return db.scalar(select(Attendance).where(Attendance.user_id == user_id, Attendance.attendance_status.in_(ACCEPTED), a, b))


def failed_attempts_today(db: Session, user_id: int) -> int:
    a, b = _today_filter()
    return db.scalar(select(func.count()).select_from(Attendance).where(
        Attendance.user_id == user_id, Attendance.attendance_status == AttendanceStatus.rejected, a, b)) or 0


def record(db: Session, user_id: int, status: AttendanceStatus, *, lat=None, lon=None, distance=None,
           confidence=None, reason=None, checkin=True) -> Attendance:
    row = Attendance(user_id=user_id, check_in_time=utcnow_naive() if checkin else None, latitude=lat, longitude=lon,
                     distance_from_campus=distance, face_confidence=confidence, attendance_status=status, reject_reason=reason)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mark_absent(db: Session, day: date) -> int:
    """Create `absent` rows for students with no accepted check-in on `day`. Idempotent."""
    s, e = day_bounds_utc(day)
    present = select(Attendance.user_id).where(Attendance.attendance_status.in_(ACCEPTED + (AttendanceStatus.absent,)),
                                              (Attendance.check_in_time >= s) & (Attendance.check_in_time < e))
    students = db.scalars(select(User).where(User.role == Role.student, User.id.not_in(present))).all()
    for u in students:
        # anchor absent rows at noon local time so they fall inside that local day
        anchor = day_bounds_utc(day)[0] + timedelta(hours=12)
        db.add(Attendance(user_id=u.id, check_in_time=anchor, attendance_status=AttendanceStatus.absent))
    db.commit()
    return len(students)
