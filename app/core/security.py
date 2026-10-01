from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(p: str) -> str:
    return _pwd.hash(p)


def verify_password(p: str, hashed: str) -> bool:
    return _pwd.verify(p, hashed)


def create_token(sub: str, purpose: str = "access", expires: timedelta | None = None, extra: dict | None = None) -> str:
    exp = datetime.now(timezone.utc) + (expires or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": sub, "purpose": purpose, "exp": exp, **(extra or {})}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, purpose: str = "access") -> dict | None:
    """Returns claims, or None if invalid/expired/wrong purpose (so an access token can't be used as a GPS token)."""
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    return claims if claims.get("purpose") == purpose else None
