from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.api.routes.attendance import _read_frames
from app.core.limiter import limiter
from app.db.session import get_db
from app.models import FaceProfile, Role, User
from app.schemas.common import Message
from app.services import antispoof, face
from app.services.audit import audit

router = APIRouter(prefix="/face", tags=["Face Profile"])


@router.get("/status")
def status(user: User = Depends(require_roles(Role.student)), db: Session = Depends(get_db)):
    return {"registered": db.scalar(select(FaceProfile).where(FaceProfile.user_id == user.id)) is not None}


@router.post("/register", response_model=Message, status_code=201,
             summary="Register your face (same blink + head-turn capture as check-in). One-time; admin must reset to re-enrol.")
@limiter.limit("5/minute")
def register(request: Request, frames: list[UploadFile] = File(...), user: User = Depends(require_roles(Role.student)),
             db: Session = Depends(get_db)):
    if db.scalar(select(FaceProfile).where(FaceProfile.user_id == user.id)):
        raise HTTPException(409, "Face already registered. Ask an admin to reset it.")
    try:
        feats = face.extract_features(_read_frames(frames))
        antispoof.verify_liveness(feats)  # don't let someone enrol a photo of somebody else
        emb = face.mean_embedding(feats)
    except face.FaceError as e:
        raise HTTPException(422, detail={"message": "Face registration failed", "reason": e.reason})
    except ImportError:
        raise HTTPException(503, "Face recognition service unavailable")
    db.add(FaceProfile(user_id=user.id, embedding_path=face.save_embedding(user.id, emb)))
    db.commit()
    audit(db, user.id, "face_register", "face_profile", user.id, request=request)
    return Message(detail="Face registered")


@router.delete("/{user_id}", response_model=Message, summary="Admin: reset a student's face profile")
def reset(user_id: int, request: Request, admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    p = db.scalar(select(FaceProfile).where(FaceProfile.user_id == user_id))
    if not p:
        raise HTTPException(404, "No face profile")
    db.delete(p)
    db.commit()
    audit(db, admin.id, "face_reset", "face_profile", user_id, request=request)
    return Message(detail="Face profile removed")
