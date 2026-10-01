import logging
from pathlib import Path

from app.core.config import settings

log = logging.getLogger(__name__)

_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def upload(path: Path, display_name: str) -> tuple[str | None, str | None]:
    """Upload to Google Drive. Returns (file_id, web_view_link) or (None, None) if disabled/failed.
    A Drive outage must never lose a student's report, so the local copy remains the source of truth."""
    if not settings.DRIVE_ENABLED:
        return None, None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive.file"])
        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        meta = {"name": display_name, "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]}
        media = MediaFileUpload(str(path), mimetype=_MIME.get(path.suffix.lower(), "application/octet-stream"))
        f = svc.files().create(body=meta, media_body=media, fields="id,webViewLink", supportsAllDrives=True).execute()
        return f["id"], f.get("webViewLink")
    except Exception:  # noqa: BLE001
        log.exception("Google Drive upload failed for %s", display_name)
        return None, None
