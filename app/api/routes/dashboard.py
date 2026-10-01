from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import Role, User
from app.services import dashboard

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
def get_dashboard(_: User = Depends(require_roles(Role.professor, Role.secretary)), db: Session = Depends(get_db)):
    return dashboard.summary(db)
