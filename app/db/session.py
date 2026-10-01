from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

_kwargs = {"connect_args": {"check_same_thread": False}} if settings.DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True, "pool_recycle": 1800}
engine = create_engine(settings.DATABASE_URL, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
