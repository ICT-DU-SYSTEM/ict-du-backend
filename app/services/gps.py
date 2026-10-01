from dataclasses import dataclass

from haversine import Unit, haversine

from app.core.config import settings


@dataclass
class GPSResult:
    distance_m: float
    inside: bool
    accuracy_ok: bool


def evaluate(lat: float, lon: float, accuracy_m: float | None) -> GPSResult:
    d = haversine((lat, lon), (settings.CAMPUS_LATITUDE, settings.CAMPUS_LONGITUDE), unit=Unit.METERS)
    accuracy_ok = accuracy_m is None or accuracy_m <= settings.MAX_GPS_ACCURACY_METERS
    return GPSResult(distance_m=round(d, 2), inside=d <= settings.ALLOWED_RADIUS_METERS, accuracy_ok=accuracy_ok)
