"""Endpoints de generacion de senales."""

from __future__ import annotations

import numpy as np
import soundfile as sf
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.generation import (
    DeviceInfoResponse,
    PinkNoiseRequest,
    PinkNoiseResponse,
    PlayRecordRequest,
    PlayRecordResponse,
    ResumenAudio,
    SineSweepRequest,
    SineSweepResponse,
    StoredAudioSamplesResponse,
)
from app.services.pink_noise import generar_ruido_rosa
from app.services.play_record import (
    device,
    guardar_audio,
    obtener_ruta_audio,
    reproducir_y_grabar,
)
from app.services.sine_sweep import generar_sine_sweep as generar_sine_sweep_service

router = APIRouter(prefix="/api/v1/generation", tags=["generation"])


@router.post(
    "/pink-noise",
    response_model=PinkNoiseResponse,
    summary="Generar ruido rosa",
)
async def generate_pink_noise(payload: PinkNoiseRequest) -> PinkNoiseResponse:
    try:
        fs = int(payload.fs)
        ruido = generar_ruido_rosa(payload.duracion, fs)
        ruta = guardar_audio(ruido, fs, payload.nombre_archivo) if payload.guardar_audio else None
        audio = _construir_resumen_audio(
            ruido,
            fs,
            ruta,
            incluir_samples=payload.incluir_samples,
            max_points=payload.max_points,
        )
        return PinkNoiseResponse(
            duracion=payload.duracion,
            fs=fs,
            audio=audio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/sine-sweep",
    response_model=SineSweepResponse,
    summary="Generar sine sweep",
)
async def generate_sine_sweep(payload: SineSweepRequest) -> SineSweepResponse:
    try:
        fs = int(payload.fs)
        sweep, filtro_inverso = generar_sine_sweep_service(
            payload.frecuencia_inicial,
            payload.frecuencia_final,
            payload.duracion,
            fs,
            payload.tipo_barrido.value,
        )
        ruta_sweep = guardar_audio(sweep, fs, payload.nombre_archivo) if payload.guardar_audio else None
        ruta_filtro = None
        if payload.guardar_filtro_inverso:
            ruta_filtro = guardar_audio(
                filtro_inverso,
                fs,
                payload.nombre_archivo_filtro_inverso,
            )
        return SineSweepResponse(
            frecuencia_inicial=payload.frecuencia_inicial,
            frecuencia_final=payload.frecuencia_final,
            duracion=payload.duracion,
            fs=fs,
            tipo_barrido=payload.tipo_barrido,
            sweep=_construir_resumen_audio(
                sweep,
                fs,
                ruta_sweep,
                incluir_samples=payload.incluir_samples,
                max_points=payload.max_points,
            ),
            filtro_inverso=_construir_resumen_audio(
                filtro_inverso,
                fs,
                ruta_filtro,
                incluir_samples=payload.incluir_samples,
                max_points=payload.max_points,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/device",
    response_model=DeviceInfoResponse,
    summary="Consultar dispositivos de audio",
)
async def get_audio_device() -> DeviceInfoResponse:
    try:
        return DeviceInfoResponse(**device())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/audio/{nombre_archivo}",
    summary="Descargar un archivo de audio generado",
)
async def get_audio_file(nombre_archivo: str) -> FileResponse:
    try:
        ruta_audio = obtener_ruta_audio(nombre_archivo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not ruta_audio.exists():
        raise HTTPException(status_code=404, detail="audio no encontrado")

    return FileResponse(
        path=ruta_audio,
        media_type="audio/wav",
        filename=ruta_audio.name,
    )


@router.get(
    "/audio/{nombre_archivo}/samples",
    response_model=StoredAudioSamplesResponse,
    summary="Obtener samples JSON de un archivo de audio generado",
)
async def get_audio_samples(nombre_archivo: str) -> StoredAudioSamplesResponse:
    try:
        ruta_audio = obtener_ruta_audio(nombre_archivo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not ruta_audio.exists():
        raise HTTPException(status_code=404, detail="audio no encontrado")

    signal, fs = sf.read(str(ruta_audio), dtype="float32", always_2d=False)
    return StoredAudioSamplesResponse(
        **_construir_resumen_audio(
            signal,
            int(fs),
            ruta_audio,
            incluir_samples=True,
            max_points=2000,
        ).model_dump()
    )


@router.post(
    "/play-record",
    response_model=PlayRecordResponse,
    summary="Reproducir y grabar una senal",
)
async def play_and_record_signal(payload: PlayRecordRequest) -> PlayRecordResponse:
    try:
        fs = int(payload.fs)
        signal = np.asarray(payload.signal, dtype=np.float32)
        grabacion = reproducir_y_grabar(signal, fs, payload.duracion_grabacion)
        ruta_grabacion = (
            guardar_audio(grabacion, fs, payload.nombre_archivo) if payload.guardar_audio else None
        )
        return PlayRecordResponse(
            fs=fs,
            duracion_grabacion=payload.duracion_grabacion,
            senal_entrada=_construir_resumen_audio(
                signal,
                fs,
                None,
                incluir_samples=payload.incluir_samples,
                max_points=payload.max_points,
            ),
            grabacion=_construir_resumen_audio(
                grabacion,
                fs,
                ruta_grabacion,
                incluir_samples=payload.incluir_samples,
                max_points=payload.max_points,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _construir_resumen_audio(
    signal: np.ndarray,
    fs: int,
    ruta_audio,
    incluir_samples: bool = True,
    max_points: int = 2000,
) -> ResumenAudio:
    signal_array = np.asarray(signal, dtype=np.float32)
    cantidad_muestras = int(signal_array.shape[0])
    if signal_array.ndim == 1:
        cantidad_canales = 1
    else:
        cantidad_canales = int(signal_array.shape[1])

    amplitude = None
    channels = None
    samples_reducidos = False
    max_points_respuesta = None

    if incluir_samples:
        signal_reducida, samples_reducidos = _reducir_para_grafico(signal_array, max_points)
        max_points_respuesta = max_points
        if signal_reducida.ndim == 1:
            amplitude = signal_reducida.tolist()
        else:
            channels = signal_reducida.T.tolist()

    valor_maximo = float(np.max(np.abs(signal_array))) if signal_array.size else 0.0
    return ResumenAudio(
        fs=fs,
        duracion=float(cantidad_muestras / fs),
        cantidad_muestras=cantidad_muestras,
        cantidad_canales=cantidad_canales,
        normalizada=valor_maximo <= 1.0,
        valor_maximo_absoluto=valor_maximo,
        audio_path=str(ruta_audio) if ruta_audio else None,
        nombre_archivo=ruta_audio.name if ruta_audio else None,
        audio_url=f"/api/v1/generation/audio/{ruta_audio.name}" if ruta_audio else None,
        amplitude=amplitude,
        channels=channels,
        samples_reducidos=samples_reducidos,
        max_points=max_points_respuesta,
    )


def _reducir_para_grafico(signal: np.ndarray, max_points: int) -> tuple[np.ndarray, bool]:
    signal_array = np.asarray(signal, dtype=np.float32)
    if max_points < 2:
        raise ValueError("max_points debe ser mayor o igual a 2")

    if signal_array.ndim == 1:
        if signal_array.shape[0] <= max_points:
            return signal_array, False
        signal_2d = signal_array[:, np.newaxis]
        reducida = _reducir_multicanal_min_max(signal_2d, max_points)
        return reducida[:, 0], True

    if signal_array.shape[0] <= max_points:
        return signal_array, False
    return _reducir_multicanal_min_max(signal_array, max_points), True


def _reducir_multicanal_min_max(signal_2d: np.ndarray, max_points: int) -> np.ndarray:
    n_samples, n_channels = signal_2d.shape
    n_bloques = max(1, max_points // 2)
    bordes = np.linspace(0, n_samples, n_bloques + 1, dtype=int)
    bloques = []

    for inicio, fin in zip(bordes[:-1], bordes[1:]):
        if fin <= inicio:
            continue
        bloque = signal_2d[inicio:fin]
        minimos = np.min(bloque, axis=0)
        maximos = np.max(bloque, axis=0)
        bloques.append(minimos)
        bloques.append(maximos)

    if not bloques:
        return signal_2d[:1]
    return np.vstack(bloques).reshape(-1, n_channels).astype(np.float32)
