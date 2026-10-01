from slowapi import Limiter
from slowapi.util import get_remote_address

# Behind nginx/Docker run uvicorn with --proxy-headers so get_remote_address sees the real client IP.
limiter = Limiter(key_func=get_remote_address)
