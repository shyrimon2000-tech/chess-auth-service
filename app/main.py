from fastapi import FastAPI

# from app.database import Base, engine
from app.routers.auth import router as auth_router
# from app import models # noqa: F401

# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Chess Auth Service"
)

app.include_router(auth_router)


@app.get("/")
def root():
    return {
        "service": "chess-game-service",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }