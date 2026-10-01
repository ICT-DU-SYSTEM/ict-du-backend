from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "ICT DU Management System"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:3000"

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    STORAGE_DIR: str = "storage"
    MAX_UPLOAD_MB: int = 10

    # ---- Campus geofence (REQUIRED: set the real Systems Plus coordinates) ----
    CAMPUS_LATITUDE: float
    CAMPUS_LONGITUDE: float
    ALLOWED_RADIUS_METERS: float = 100
    MAX_GPS_ACCURACY_METERS: float = 50
    GPS_TOKEN_EXPIRE_SECONDS: int = 120

    # ---- Attendance schedule (local time) ----
    TIMEZONE: str = "Asia/Manila"
    ATTENDANCE_START: str = "08:00"
    LATE_AFTER: str = "08:15"
    MAX_FAILED_FACE_ATTEMPTS_PER_DAY: int = 5

    # ---- Face recognition / liveness ----
    FACE_MATCH_THRESHOLD: float = 0.45   # cosine similarity, ArcFace embeddings
    FACE_MIN_DET_SCORE: float = 0.6
    LIVENESS_REQUIRE_BLINK: bool = True
    LIVENESS_REQUIRE_HEAD_MOVEMENT: bool = True
    LIVENESS_MIN_YAW_RANGE_DEG: float = 12.0
    LIVENESS_BLINK_DROP_RATIO: float = 0.65
    ANTISPOOF_REQUIRE_PASSIVE: bool = True
    ANTISPOOF_MODEL_PATHS: str = ""       # "models/2.7_80x80_MiniFASNetV2.onnx:2.7,models/4_0_80x80_MiniFASNetV1SE.onnx:4.0"
    ANTISPOOF_THRESHOLD: float = 0.7

    # ---- Google Drive ----
    DRIVE_ENABLED: bool = False
    GOOGLE_SERVICE_ACCOUNT_FILE: str = ""
    GOOGLE_DRIVE_FOLDER_ID: str = ""

    @model_validator(mode="after")
    def _check(self):
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if self.CAMPUS_LATITUDE == 0 and self.CAMPUS_LONGITUDE == 0:
            raise ValueError("Set CAMPUS_LATITUDE / CAMPUS_LONGITUDE to the real campus coordinates")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
