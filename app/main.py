import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import wait_for_db
from app.limiter import limiter
from app.routers.auth import router as auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    logger.info("chess-auth-service started")
    yield


app = FastAPI(
    title="Chess Auth Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.include_router(auth_router)


@app.get("/")
def root():
    return {
        "service": "chess-auth-service",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }
