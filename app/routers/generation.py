"""Endpoints de generacion de senales — flujo directo (audio como binario)."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.generation import (
    AudioSamplesResponse,
    DeviceInfoResponse,
    PinkNoiseAudioRequest,
    RecordingStatusResponse,
    SineSweepAudioRequest,
    StartRecordingRequest,
    StartRecordingResponse,
)
from app.services.pink_noise import generar_ruido_rosa
from app.services.play_record import (
    device,
    detener_grabacion,
    estado_grabacion,
    iniciar_grabacion,
)
from app.services.sine_sweep import generar_sine_sweep as generar_sine_sweep_service

router = APIRouter(prefix="/api/v1/generation", tags=["generation"])


def _a_wav(signal: np.ndarray, fs: int) -> io.BytesIO:
    buf = io.BytesIO()
    sf.write(buf, signal, fs, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf


def _wav_response(buf: io.BytesIO, filename: str) -> StreamingResponse:
    return StreamingResponse(
        buf,
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/pink-noise", summary="Generar ruido rosa y devolver WAV")
async def generate_pink_noise(payload: PinkNoiseAudioRequest) -> StreamingResponse:
    try:
        signal = generar_ruido_rosa(payload.duracion, int(payload.fs))
        return _wav_response(_a_wav(signal, int(payload.fs)), "pink_noise.wav")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sine-sweep", summary="Generar sine sweep y devolver WAV")
async def generate_sine_sweep(payload: SineSweepAudioRequest) -> StreamingResponse:
    try:
        fs = int(payload.fs)
        sweep, _ = generar_sine_sweep_service(
            payload.frecuencia_inicial,
            payload.frecuencia_final,
            payload.duracion,
            fs,
            payload.tipo_barrido.value,
        )
        return _wav_response(_a_wav(sweep, fs), "sine_sweep.wav")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sine-sweep/inverse-filter", summary="Generar filtro inverso del sine sweep")
async def generate_inverse_filter(payload: SineSweepAudioRequest) -> StreamingResponse:
    try:
        fs = int(payload.fs)
        _, filtro = generar_sine_sweep_service(
            payload.frecuencia_inicial,
            payload.frecuencia_final,
            payload.duracion,
            fs,
            payload.tipo_barrido.value,
        )
        return _wav_response(_a_wav(filtro, fs), "inverse_filter.wav")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upload-recording", summary="Recibir grabacion del navegador y devolverla")
async def upload_recording(file: UploadFile = File(...)) -> StreamingResponse:
    content = await file.read()
    return StreamingResponse(
        io.BytesIO(content),
        media_type=file.content_type or "audio/wav",
        headers={"Content-Disposition": f"attachment; filename={file.filename or 'grabacion.wav'}"},
    )


@router.post("/samples", summary="Extraer muestras de un audio para visualizacion")
async def get_audio_samples(
    file: UploadFile = File(...),
    n_puntos: int = Query(2000, ge=100, le=10000),
) -> AudioSamplesResponse:
    try:
        arr, fs = sf.read(io.BytesIO(await file.read()), dtype="float32", always_2d=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el audio: {exc}") from exc

    arr = np.asarray(arr, dtype=np.float32)
    n_canales = 1 if arr.ndim == 1 else arr.shape[1]
    reducida, fue_reducida = _reducir_para_grafico(arr, n_puntos)

    return AudioSamplesResponse(
        fs=int(fs),
        duracion=float(arr.shape[0] / fs),
        n_canales=n_canales,
        samples_reducidos=fue_reducida,
        amplitude=reducida.tolist() if reducida.ndim == 1 else None,
        channels=reducida.T.tolist() if reducida.ndim > 1 else None,
    )


@router.get("/device", response_model=DeviceInfoResponse, summary="Dispositivos de audio")
async def get_audio_device() -> DeviceInfoResponse:
    try:
        return DeviceInfoResponse(**device())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/recording/status", response_model=RecordingStatusResponse)
async def get_recording_status() -> RecordingStatusResponse:
    return RecordingStatusResponse(**estado_grabacion())


@router.post("/recording/start", response_model=StartRecordingResponse)
async def start_recording(payload: StartRecordingRequest) -> StartRecordingResponse:
    try:
        estado = iniciar_grabacion(
            fs=int(payload.fs),
            canales=payload.canales,
            input_device=payload.input_device,
            nombre_archivo=payload.nombre_archivo,
            auto_stop_seconds=payload.auto_stop_seconds,
        )
        return StartRecordingResponse(estado=RecordingStatusResponse(**estado))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/recording/stop", summary="Detener grabacion del servidor y devolver WAV")
async def stop_recording() -> StreamingResponse:
    try:
        audio, fs, _ruta, _estado = detener_grabacion(guardar_archivo=False)
        return _wav_response(_a_wav(audio, fs), "grabacion_servidor.wav")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _reducir_para_grafico(signal: np.ndarray, max_points: int) -> tuple[np.ndarray, bool]:
    arr = np.asarray(signal, dtype=np.float32)
    if arr.ndim == 1:
        if arr.shape[0] <= max_points:
            return arr, False
        return _reducir_multicanal_min_max(arr[:, np.newaxis], max_points)[:, 0], True
    if arr.shape[0] <= max_points:
        return arr, False
    return _reducir_multicanal_min_max(arr, max_points), True


def _reducir_multicanal_min_max(signal_2d: np.ndarray, max_points: int) -> np.ndarray:
    n_samples, n_channels = signal_2d.shape
    n_bloques = max(1, max_points // 2)
    bordes = np.linspace(0, n_samples, n_bloques + 1, dtype=int)
    bloques = []
    for inicio, fin in zip(bordes[:-1], bordes[1:]):
        if fin <= inicio:
            continue
        bloque = signal_2d[inicio:fin]
        bloques.append(np.min(bloque, axis=0))
        bloques.append(np.max(bloque, axis=0))
    if not bloques:
        return signal_2d[:1]
    return np.vstack(bloques).reshape(-1, n_channels).astype(np.float32)
