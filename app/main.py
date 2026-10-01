import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import setup_logging

setup_logging()
log = logging.getLogger("app")

app = FastAPI(title=settings.APP_NAME, version="1.0.0",
              docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
              redoc_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def access_log(request: Request, call_next):
    t = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, resp.status_code, (time.perf_counter() - t) * 1000)
    return resp


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


app.include_router(api, prefix=settings.API_PREFIX)

print("\n=== Registered Route ===")
for route in app.routes:
    if hasattr(route, "path"):
        print(route.path)

