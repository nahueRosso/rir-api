"""Endpoints placeholder para el modulo de analisis acustico."""

from fastapi import APIRouter

from app.schemas.common import PlaceholderRequest, PlaceholderResponse
from app.services.placeholders import placeholder_response

router = APIRouter(prefix="/api/v1/acoustics", tags=["acoustics"])


@router.post(
    "/schroeder",
    response_model=PlaceholderResponse,
    summary="Calcular integral de Schroeder",
)
async def schroeder_integral(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/linear-regression",
    response_model=PlaceholderResponse,
    summary="Calcular regresion lineal",
)
async def linear_regression(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/parameters",
    response_model=PlaceholderResponse,
    summary="Calcular parametros acusticos",
)
async def acoustic_parameters(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())


@router.post(
    "/lundeby",
    response_model=PlaceholderResponse,
    summary="Estimar truncamiento por Lundeby",
)
async def lundeby_method(payload: PlaceholderRequest) -> PlaceholderResponse:
    _ = payload
    return PlaceholderResponse(**placeholder_response())
