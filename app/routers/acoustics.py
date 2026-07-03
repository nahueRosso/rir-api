"""Endpoints de analisis de parametros acusticos (Milestone 3)."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.schemas.acoustics import (
    AcousticParametersResponse,
    LinearRegressionRequest,
    LinearRegressionResponse,
    LundebyResponse,
    SchroederResponse,
    SmoothingResponse,
)
from app.services.acoustic_parameters import (
    calcular_parametros_acusticos,
    integral_schroeder,
    metodo_lundeby,
    regresion_lineal,
    suavizar_signal,
)

router = APIRouter(prefix="/api/v1/acoustics", tags=["acoustics"])


def _leer_audio(file: UploadFile) -> tuple[np.ndarray, int]:
    """Lee un UploadFile y devuelve (senal float64 mono, fs)."""
    try:
        senal, fs = sf.read(io.BytesIO(file.file.read()), dtype="float64", always_2d=False)
    except Exception as exc:
        detalle = f"No se pudo leer '{file.filename}': {exc}"
        raise HTTPException(status_code=400, detail=detalle) from exc

    senal = np.asarray(senal, dtype=np.float64)
    if senal.ndim > 1:
        senal = senal.mean(axis=1)
    return senal, int(fs)


@router.post(
    "/smoothing",
    response_model=SmoothingResponse,
    summary="Suavizar una senal (envolvente de Hilbert o media movil)",
)
async def smoothing(
    file: UploadFile = File(...),
    ventana: str = Query(
        "hilbert", description="'hilbert' o un entero (tamano de ventana en muestras)"
    ),
) -> SmoothingResponse:
    senal, fs = _leer_audio(file)

    ventana_param: int | str = ventana
    if ventana != "hilbert":
        try:
            ventana_param = int(ventana)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="ventana debe ser 'hilbert' o un entero"
            ) from exc

    try:
        envolvente = suavizar_signal(senal, ventana_param)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tiempo = (np.arange(len(envolvente)) / fs).tolist()
    return SmoothingResponse(
        fs=fs, ventana=str(ventana), tiempo=tiempo, envolvente=envolvente.tolist()
    )


@router.post(
    "/schroeder",
    response_model=SchroederResponse,
    summary="Calcular integral de Schroeder (curva de decaimiento en dB)",
)
async def schroeder_integral(file: UploadFile = File(...)) -> SchroederResponse:
    senal, fs = _leer_audio(file)

    try:
        edc_db = integral_schroeder(senal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tiempo = (np.arange(len(edc_db)) / fs).tolist()
    return SchroederResponse(fs=fs, tiempo=tiempo, edc_db=edc_db.tolist())


@router.post(
    "/linear-regression",
    response_model=LinearRegressionResponse,
    summary="Calcular regresion lineal por minimos cuadrados",
)
async def linear_regression(payload: LinearRegressionRequest) -> LinearRegressionResponse:
    try:
        pendiente, ordenada, r_cuadrado = regresion_lineal(payload.x, payload.y)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LinearRegressionResponse(
        pendiente=pendiente, ordenada_al_origen=ordenada, r_cuadrado=r_cuadrado
    )


@router.post(
    "/parameters",
    response_model=AcousticParametersResponse,
    summary="Calcular parametros acusticos ISO 3382 por banda de octava",
)
async def acoustic_parameters(file: UploadFile = File(...)) -> AcousticParametersResponse:
    senal, fs = _leer_audio(file)

    try:
        parametros = calcular_parametros_acusticos(senal, fs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AcousticParametersResponse(fs=fs, parametros=parametros)


@router.post(
    "/lundeby",
    response_model=LundebyResponse,
    summary="Estimar truncamiento por el metodo de Lundeby",
)
async def lundeby_method(file: UploadFile = File(...)) -> LundebyResponse:
    senal, fs = _leer_audio(file)

    try:
        indice, nivel_ruido = metodo_lundeby(senal, fs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LundebyResponse(
        fs=fs,
        indice_truncamiento=indice,
        tiempo_truncamiento=float(indice / fs),
        nivel_ruido_db=nivel_ruido,
    )
