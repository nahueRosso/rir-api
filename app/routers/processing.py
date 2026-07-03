"""Endpoints de procesamiento de la respuesta al impulso (Milestone 2)."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.processing import LogScaleResponse, SynthesizeRiRequest
from app.services.filter import filtro_octava
from app.services.signal_utils import a_escala_log, obtener_ri_desde_sweep, sintetizar_ri

router = APIRouter(prefix="/api/v1/processing", tags=["processing"])

BANDAS_OCTAVA = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]


def _leer_audio(file: UploadFile) -> tuple[np.ndarray, int]:
    """Lee un UploadFile y devuelve (senal float32, fs)."""
    try:
        senal, fs = sf.read(io.BytesIO(file.file.read()), dtype="float32", always_2d=False)
        return np.asarray(senal, dtype=np.float32), int(fs)
    except Exception as exc:
        detalle = f"No se pudo leer '{file.filename}': {exc}"
        raise HTTPException(status_code=400, detail=detalle) from exc


def _a_wav(senal: np.ndarray, fs: int) -> io.BytesIO:
    buf = io.BytesIO()
    sf.write(buf, senal, fs, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf


def _wav_response(buf: io.BytesIO, filename: str) -> StreamingResponse:
    return StreamingResponse(
        buf,
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/impulse-response", summary="Deconvolucion: grabacion + filtro inverso → RI")
async def impulse_response_from_sweep(
    grabacion: UploadFile = File(..., description="WAV de la grabacion del sweep en la sala"),
    filtro_inverso: UploadFile = File(..., description="WAV del filtro inverso del sweep"),
) -> StreamingResponse:
    senal_grab, fs = _leer_audio(grabacion)
    senal_filtro, fs_fi = _leer_audio(filtro_inverso)

    if fs != fs_fi:
        raise HTTPException(
            status_code=400,
            detail=f"Las frecuencias de muestreo no coinciden: {fs} Hz vs {fs_fi} Hz",
        )

    try:
        ri = obtener_ri_desde_sweep(senal_grab, senal_filtro)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _wav_response(_a_wav(ri, fs), "impulse_response.wav")


@router.post("/octave-filter", summary="Filtrar RI por banda de octava")
async def octave_filter(
    file: UploadFile = File(...),
    fc: float = Query(..., description="Frecuencia central de la banda en Hz"),
    orden: int = Query(4, ge=1, le=10),
) -> StreamingResponse:
    senal, fs = _leer_audio(file)

    try:
        filtrada = filtro_octava(senal, fc, fs, orden)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    nombre = f"banda_{int(fc)}Hz.wav"
    return _wav_response(_a_wav(filtrada, fs), nombre)


@router.post("/log-scale", summary="Convertir RI a escala logaritmica (dB)")
async def log_scale(
    file: UploadFile = File(...),
    n_puntos: int = Query(4000, ge=100, le=20000),
) -> LogScaleResponse:
    senal, fs = _leer_audio(file)

    try:
        db = a_escala_log(senal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    n = len(db)
    # Downsample for response size
    if n > n_puntos:
        indices = np.round(np.linspace(0, n - 1, n_puntos)).astype(int)
        db_out = db[indices]
        tiempo = (indices / fs).tolist()
    else:
        db_out = db
        tiempo = (np.arange(n) / fs).tolist()

    return LogScaleResponse(
        fs=fs,
        duracion=float(n / fs),
        n_muestras=n,
        tiempo=tiempo,
        db=db_out.tolist(),
    )


@router.post("/synthesize-ri", summary="Sintetizar RI con T60 conocidos por banda")
async def synthesize_ri(payload: SynthesizeRiRequest) -> StreamingResponse:
    try:
        t60_float = {float(k): v for k, v in payload.t60_por_banda.items()}
        ri = sintetizar_ri(t60_float, payload.fs, payload.duracion)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _wav_response(_a_wav(ri, payload.fs), "ri_sintetizada.wav")
