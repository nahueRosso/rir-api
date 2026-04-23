"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.common import HealthResponse
from app.settings import get_settings

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse, summary="Estado de salud de la API")
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )
