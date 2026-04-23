"""Endpoints placeholder para el modulo de generacion."""

from fastapi import APIRouter

from app.schemas.common import PlaceholderRequest, PlaceholderResponse
from app.services.placeholders import placeholder_response

router = APIRouter(prefix="/api/v1/generation", tags=["generation"])


@router.post(
    "/pink-noise",
    response_model=PlaceholderResponse,
    summary="Generar ruido rosa",
)
async def generate_pink_noise(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/sine-sweep",
    response_model=PlaceholderResponse,
    summary="Generar sine sweep logaritmico",
)
async def generate_sine_sweep(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/play-record",
    response_model=PlaceholderResponse,
    summary="Reproducir y grabar una senal",
)
async def play_and_record_signal(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())
