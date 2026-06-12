from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import wait_for_db
from app.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    yield


app = FastAPI(
    title="Chess Auth Service",
    version="1.0.0",
    lifespan=lifespan,
)

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
