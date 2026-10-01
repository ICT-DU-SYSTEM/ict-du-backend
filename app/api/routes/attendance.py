import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import create_token, decode_token
from app.core.timeutil import day_bounds_utc, local_now, utcnow_naive
from app.db.session import get_db
from app.models import Attendance, AttendanceStatus, FaceProfile, Role, User
from app.schemas.attendance import AttendanceOut, GPSIn, GPSOut
from app.schemas.common import Message
from app.services import antispoof, face, gps
from app.services import attendance as svc
from app.services.audit import audit

log = logging.getLogger(__name__)
router = APIRouter(prefix="/attendance", tags=["Attendance"])
student = require_roles(Role.student)
viewers = require_roles(Role.professor, Role.secretary)

MIN_FRAMES, MAX_FRAMES, MAX_FRAME_BYTES = 4, 12, 1_500_000


@router.post("/gps-check", response_model=GPSOut,
             summary="STEP 1 - GPS verification. Only a successful result enables the camera and returns the token step 2 requires.")
@limiter.limit("10/minute")
def gps_check(request: Request, body: GPSIn, user: User = Depends(student), db: Session = Depends(get_db)):
    if not db.scalar(select(FaceProfile).where(FaceProfile.user_id == user.id)):
        raise HTTPException(409, "Register your face before submitting attendance")
    if svc.accepted_today(db, user.id):
        raise HTTPException(409, "Attendance already recorded today")
    if svc.failed_attempts_today(db, user.id) >= settings.MAX_FAILED_FACE_ATTEMPTS_PER_DAY:
        raise HTTPException(429, "Too many rejected attempts today; contact your professor")

    res = gps.evaluate(body.latitude, body.longitude, body.accuracy_m)
    if not res.accuracy_ok:
        raise HTTPException(422, f"GPS accuracy too low (must be within {settings.MAX_GPS_ACCURACY_METERS:.0f} m). Move to an open area and retry.")
    if not res.inside:  # RULE 1 + 2: reject, camera stays disabled
        svc.record(db, user.id, AttendanceStatus.rejected, lat=body.latitude, lon=body.longitude, distance=res.distance_m, reason="outside_campus")
        raise HTTPException(403, detail={"message": "Outside campus radius; attendance rejected", "camera_enabled": False, "distance_m": res.distance_m})

    token = create_token(str(user.id), "gps", timedelta(seconds=settings.GPS_TOKEN_EXPIRE_SECONDS),
                         {"lat": body.latitude, "lon": body.longitude, "dist": res.distance_m})
    return GPSOut(camera_enabled=True, distance_m=res.distance_m, attendance_token=token, expires_in=settings.GPS_TOKEN_EXPIRE_SECONDS)


def _read_frames(files: list[UploadFile]) -> list:
    if not MIN_FRAMES <= len(files) <= MAX_FRAMES:
        raise HTTPException(422, f"Send between {MIN_FRAMES} and {MAX_FRAMES} frames captured over ~3 seconds")
    out = []
    for f in files:
        data = f.file.read(MAX_FRAME_BYTES + 1)
        if len(data) > MAX_FRAME_BYTES:
            raise HTTPException(413, "Frame too large; downscale to ~640px JPEG")
        out.append(face.decode_image(data))
    return out


@router.post("/check-in", response_model=AttendanceOut,
             summary="STEP 2 - Face verification + liveness. Requires the token from /gps-check.")
@limiter.limit("10/minute")
def check_in(request: Request, attendance_token: str = Form(...), frames: list[UploadFile] = File(...),
             user: User = Depends(student), db: Session = Depends(get_db)):
    claims = decode_token(attendance_token, "gps")
    if not claims or claims["sub"] != str(user.id):
        raise HTTPException(403, "GPS verification missing or expired; run /attendance/gps-check first")
    if svc.accepted_today(db, user.id):
        raise HTTPException(409, "Attendance already recorded today")
    if svc.failed_attempts_today(db, user.id) >= settings.MAX_FAILED_FACE_ATTEMPTS_PER_DAY:
        raise HTTPException(429, "Too many rejected attempts today; contact your professor")
    profile = db.scalar(select(FaceProfile).where(FaceProfile.user_id == user.id))
    if not profile:
        raise HTTPException(409, "Register your face first")

    ctx = dict(lat=claims["lat"], lon=claims["lon"], distance=claims["dist"])
    try:
        try:
            feats = face.extract_features(_read_frames(frames))
            antispoof.verify_liveness(feats)
            conf = face.cosine(face.mean_embedding(feats), face.load_embedding(profile.embedding_path))
            if conf < settings.FACE_MATCH_THRESHOLD:
                raise face.FaceError("face_not_recognized")
        except face.FaceError as e:
            row = svc.record(db, user.id, AttendanceStatus.rejected, reason=e.reason, **ctx)
            audit(db, user.id, "attendance_rejected", "attendance", row.id, e.reason, request)
            raise HTTPException(401, detail={"message": "Face verification failed", "reason": e.reason})
    except ImportError:
        log.exception("ML dependencies missing")
        raise HTTPException(503, "Face recognition service unavailable")

    row = svc.record(db, user.id, svc.status_for_now(), confidence=round(conf, 4), **ctx)
    audit(db, user.id, "attendance_ok", "attendance", row.id, row.attendance_status.value, request)
    return row


@router.post("/check-out", response_model=AttendanceOut, summary="Check out (must be on campus)")
@limiter.limit("10/minute")
def check_out(request: Request, body: GPSIn, user: User = Depends(student), db: Session = Depends(get_db)):
    row = svc.accepted_today(db, user.id)
    if not row:
        raise HTTPException(409, "No check-in found for today")
    if row.check_out_time:
        raise HTTPException(409, "Already checked out")
    res = gps.evaluate(body.latitude, body.longitude, body.accuracy_m)
    if not res.accuracy_ok or not res.inside:
        raise HTTPException(403, "You must be on campus (with a reliable GPS fix) to check out")
    row.check_out_time = utcnow_naive()
    db.commit()
    return row


@router.get("/me", response_model=list[AttendanceOut])
def my_attendance(skip: int = 0, limit: int = Query(50, le=200), user: User = Depends(student), db: Session = Depends(get_db)):
    return db.scalars(select(Attendance).where(Attendance.user_id == user.id).order_by(Attendance.id.desc()).offset(skip).limit(limit)).all()


@router.get("", response_model=list[AttendanceOut], summary="Professor/secretary/admin view")
def list_attendance(day: date | None = None, user_id: int | None = None, status: AttendanceStatus | None = None,
                    skip: int = 0, limit: int = Query(100, le=500), _: User = Depends(viewers), db: Session = Depends(get_db)):
    q = select(Attendance).order_by(Attendance.id.desc()).offset(skip).limit(limit)
    if day:
        s, e = day_bounds_utc(day)
        q = q.where(Attendance.check_in_time >= s, Attendance.check_in_time < e)
    if user_id:
        q = q.where(Attendance.user_id == user_id)
    if status:
        q = q.where(Attendance.attendance_status == status)
    return db.scalars(q).all()


@router.post("/mark-absent", response_model=Message, summary="Mark students without a check-in as absent (run after the cut-off)")
def mark_absent(day: date | None = None, user: User = Depends(require_roles(Role.professor)), db: Session = Depends(get_db)):
    d = day or local_now().date()
    n = svc.mark_absent(db, d)
    return Message(detail=f"{n} student(s) marked absent for {d}")
