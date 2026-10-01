import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings

ALLOWED = {".pdf": b"%PDF", ".docx": b"PK\x03\x04"}  # extension -> magic bytes


def _root(sub: str) -> Path:
    p = Path(settings.STORAGE_DIR) / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_document(file: UploadFile, sub: str) -> tuple[Path, str]:
    """Validate (extension + magic bytes + size) and store under a random name. Returns (path, original_name)."""
    name = file.filename or "upload"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, "Only PDF and DOCX files are accepted")
    data = file.file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_MB} MB")
    if not data.startswith(ALLOWED[ext]):
        raise HTTPException(415, "File content does not match its extension")
    dest = _root(sub) / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(data)
    return dest, name


def embeddings_dir() -> Path:
    return _root("embeddings")
