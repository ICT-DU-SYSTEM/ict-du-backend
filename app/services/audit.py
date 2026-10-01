from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, user_id: int | None, action: str, entity: str | None = None, entity_id: int | None = None,
          detail: str | None = None, request: Request | None = None) -> None:
    ip = request.client.host if request and request.client else None
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, detail=detail, ip=ip))
    db.commit()
