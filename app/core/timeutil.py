from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings

TZ = ZoneInfo(settings.TIMEZONE)


def local_now() -> datetime:
    return datetime.now(TZ)


def utcnow_naive() -> datetime:
    """DB stores naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=TZ)
    end = start + timedelta(days=1)
    to_utc = lambda x: x.astimezone(timezone.utc).replace(tzinfo=None)
    return to_utc(start), to_utc(end)


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))
