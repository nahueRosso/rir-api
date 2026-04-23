"""Endpoints placeholder para el modulo de procesamiento."""

from fastapi import APIRouter

from app.schemas.common import PlaceholderRequest, PlaceholderResponse
from app.services.placeholders import placeholder_response

router = APIRouter(prefix="/api/v1/processing", tags=["processing"])


@router.post(
    "/load-audio",
    response_model=PlaceholderResponse,
    summary="Cargar un archivo de audio",
)
async def load_audio(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/impulse-response-from-sweep",
    response_model=PlaceholderResponse,
    summary="Obtener RI desde un sweep",
)
async def impulse_response_from_sweep(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/octave-filter",
    response_model=PlaceholderResponse,
    summary="Aplicar filtro de octava",
)
async def octave_filter(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/log-scale",
    response_model=PlaceholderResponse,
    summary="Convertir senal a escala log",
)
async def log_scale(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/synthesize-ri",
    response_model=PlaceholderResponse,
    summary="Sintetizar una RI",
)
async def synthesize_ri(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())
