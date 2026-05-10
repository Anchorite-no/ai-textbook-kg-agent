from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, version="0.1.0")
