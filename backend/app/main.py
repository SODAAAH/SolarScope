from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings, get_allowed_origins
from backend.app.storage.db import init_db
from backend.app.api.endpoints import router as api_router

init_db()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Evidence-based solar photovoltaic, battery storage and whole-system analytics platform."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Project-Id"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": "/api/health"
    }
