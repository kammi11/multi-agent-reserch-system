from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import evaluate, export, research

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=settings.tagline,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research.router)
app.include_router(export.router)
app.include_router(evaluate.router)


@app.get("/")
async def root():
    return {"app": settings.app_name, "tagline": settings.tagline, "docs": "/docs"}
