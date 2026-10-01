from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Archive, ArchiveCategory, Report, ReportStage, ReportStatus, Role, User
from app.schemas.common import Message
from app.schemas.report import ArchiveOut, ProfessorReview, ReportOut, SecretaryReview
from app.services import drive, storage
from app.services.audit import audit

router = APIRouter(prefix="/reports", tags=["Reports"])
reviewers = (Role.secretary, Role.professor)


def _report(db: Session, rid: int, user: User) -> Report:
    r = db.get(Report, rid)
    if not r:
        raise HTTPException(404, "Report not found")
    if user.role == Role.student and r.user_id != user.id:
        raise HTTPException(403, "Insufficient permissions")
    return r


@router.post("", response_model=ReportOut, status_code=201, summary="Student uploads a PDF/DOCX report")
def upload_report(request: Request, title: str = Form(..., max_length=200), file: UploadFile = File(...),
                  user: User = Depends(require_roles(Role.student)), db: Session = Depends(get_db)):
    path, original = storage.save_document(file, "reports")
    fid, url = drive.upload(path, f"{user.id}_{title}{path.suffix}")
    r = Report(title=title, file_path=str(path), drive_file_id=fid, drive_url=url, user_id=user.id)
    db.add(r)
    db.commit()
    audit(db, user.id, "report_upload", "report", r.id, original, request)
    return r


@router.get("", response_model=list[ReportOut])
def list_reports(status: ReportStatus | None = None, stage: ReportStage | None = None, skip: int = 0,
                 limit: int = Query(50, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Report).order_by(Report.created_at.desc()).offset(skip).limit(limit)
    if user.role == Role.student:
        q = q.where(Report.user_id == user.id)
    if status:
        q = q.where(Report.status == status)
    if stage:
        q = q.where(Report.stage == stage)
    return db.scalars(q).all()


@router.get("/{rid}", response_model=ReportOut)
def get_report(rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _report(db, rid, user)


@router.get("/{rid}/download", summary="Download / print the original file")
def download(rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _report(db, rid, user)
    p = Path(r.file_path)
    if not p.exists():
        raise HTTPException(410, "File missing from storage")
    return FileResponse(p, filename=f"{r.title}{p.suffix}")


@router.post("/{rid}/secretary-review", response_model=ReportOut)
def secretary_review(rid: int, body: SecretaryReview, request: Request,
                     user: User = Depends(require_roles(Role.secretary)), db: Session = Depends(get_db)):
    r = _report(db, rid, user)
    if r.stage != ReportStage.pending_secretary:
        raise HTTPException(409, f"Report is at stage '{r.stage.value}'")
    if body.decision == "forward":
        r.stage = ReportStage.pending_professor
    else:
        r.status, r.stage = ReportStatus.rejected, ReportStage.completed
    r.remarks = body.remarks
    db.commit()
    audit(db, user.id, f"report_secretary_{body.decision}", "report", r.id, request=request)
    return r


@router.post("/{rid}/professor-review", response_model=ReportOut)
def professor_review(rid: int, body: ProfessorReview, request: Request,
                     user: User = Depends(require_roles(Role.professor)), db: Session = Depends(get_db)):
    r = _report(db, rid, user)
    if r.stage != ReportStage.pending_professor:
        raise HTTPException(409, f"Report is at stage '{r.stage.value}' (needs secretary review first)")
    r.remarks = body.remarks
    r.stage = ReportStage.completed
    if body.decision == "approve":
        r.status = ReportStatus.approved
        db.add(Archive(name=r.title, category=ArchiveCategory.report, file_path=r.file_path,
                       drive_file_id=r.drive_file_id, drive_url=r.drive_url, uploaded_by=r.user_id))  # auto-archive
    else:
        r.status = ReportStatus.rejected
    db.commit()
    audit(db, user.id, f"report_professor_{body.decision}", "report", r.id, request=request)
    return r


@router.delete("/{rid}", response_model=Message)
def delete_report(rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _report(db, rid, user)
    if user.role == Role.student and r.stage != ReportStage.pending_secretary:
        raise HTTPException(409, "You can only withdraw a report before it is reviewed")
    if user.role in reviewers:
        raise HTTPException(403, "Insufficient permissions")
    db.delete(r)
    db.commit()
    return Message(detail="Report deleted")


# ---------------- Archives ----------------
archives = APIRouter(prefix="/archives", tags=["Archives"])
archivist = require_roles(Role.secretary, Role.professor)


@archives.get("", response_model=list[ArchiveOut])
def list_archives(category: ArchiveCategory | None = None, skip: int = 0, limit: int = Query(50, le=200),
                  _: User = Depends(archivist), db: Session = Depends(get_db)):
    q = select(Archive).order_by(Archive.created_at.desc()).offset(skip).limit(limit)
    if category:
        q = q.where(Archive.category == category)
    return db.scalars(q).all()


@archives.post("", response_model=ArchiveOut, status_code=201)
def create_archive(name: str = Form(..., max_length=200), category: ArchiveCategory = Form(...), file: UploadFile = File(...),
                   user: User = Depends(archivist), db: Session = Depends(get_db)):
    path, _ = storage.save_document(file, "archives")
    fid, url = drive.upload(path, f"{category.value}_{name}{path.suffix}")
    a = Archive(name=name, category=category, file_path=str(path), drive_file_id=fid, drive_url=url, uploaded_by=user.id)
    db.add(a)
    db.commit()
    return a


@archives.get("/{aid}/download")
def download_archive(aid: int, _: User = Depends(archivist), db: Session = Depends(get_db)):
    a = db.get(Archive, aid)
    if not a:
        raise HTTPException(404, "Archive not found")
    p = Path(a.file_path)
    if not p.exists():
        raise HTTPException(410, "File missing from storage")
    return FileResponse(p, filename=f"{a.name}{p.suffix}")


@archives.delete("/{aid}", response_model=Message)
def delete_archive(aid: int, _: User = Depends(require_roles()), db: Session = Depends(get_db)):
    a = db.get(Archive, aid)
    if not a:
        raise HTTPException(404, "Archive not found")
    db.delete(a)
    db.commit()
    return Message(detail="Archive deleted")
