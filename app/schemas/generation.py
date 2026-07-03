from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SampleRateHz(IntEnum):
    HZ_8000 = 8000
    HZ_16000 = 16000
    HZ_22050 = 22050
    HZ_32000 = 32000
    HZ_44100 = 44100
    HZ_48000 = 48000
    HZ_88200 = 88200
    HZ_96000 = 96000
    HZ_176400 = 176400
    HZ_192000 = 192000


class TipoBarrido(StrEnum):
    LINEAL = "lineal"
    LOGARITMICO = "logaritmico"


class ResumenAudio(BaseModel):
    fs: int
    duracion: float
    cantidad_muestras: int
    cantidad_canales: int
    normalizada: bool
    valor_maximo_absoluto: float
    audio_path: str | None = None
    nombre_archivo: str | None = None
    audio_url: str | None = None
    amplitude: list[float] | None = None
    channels: list[list[float]] | None = None
    samples_reducidos: bool = False
    max_points: int | None = None


class PinkNoiseRequest(BaseModel):
    duracion: float = Field(..., gt=0)
    fs: SampleRateHz
    guardar_audio: bool = True
    nombre_archivo: str = "ruido_rosa.wav"
    incluir_samples: bool = True
    max_points: int = Field(2000, ge=2, le=20000)


class PinkNoiseResponse(BaseModel):
    tipo: str = "pink_noise"
    duracion: float
    fs: int
    audio: ResumenAudio


class SineSweepRequest(BaseModel):
    frecuencia_inicial: float = Field(..., gt=0)
    frecuencia_final: float = Field(..., gt=0)
    duracion: float = Field(..., gt=0)
    fs: SampleRateHz
    tipo_barrido: TipoBarrido = TipoBarrido.LOGARITMICO
    guardar_audio: bool = True
    nombre_archivo: str = "sine_sweep.wav"
    guardar_filtro_inverso: bool = True
    nombre_archivo_filtro_inverso: str = "sine_sweep_inverso.wav"
    incluir_samples: bool = True
    max_points: int = Field(2000, ge=2, le=20000)


class SineSweepResponse(BaseModel):
    tipo: str = "sine_sweep"
    frecuencia_inicial: float
    frecuencia_final: float
    duracion: float
    fs: int
    tipo_barrido: TipoBarrido
    sweep: ResumenAudio
    filtro_inverso: ResumenAudio


class DeviceInfoResponse(BaseModel):
    default_input_device: int | None
    default_output_device: int | None
    devices: list[dict[str, Any]]


class StartRecordingRequest(BaseModel):
    fs: SampleRateHz
    canales: int = Field(1, ge=1, le=32)
    input_device: int | None = None
    nombre_archivo: str = "grabacion_manual.wav"
    auto_stop_seconds: float = Field(60.0, gt=0, le=3600)


class RecordingStatusResponse(BaseModel):
    recording: bool
    fs: int | None = None
    canales: int | None = None
    input_device: int | None = None
    nombre_archivo: str | None = None
    duracion_actual: float = 0.0
    auto_stop_seconds: float | None = None
    ultimo_archivo_guardado: str | None = None
    ultimo_motivo_fin: str | None = None
    ultima_duracion_grabada: float = 0.0


class StartRecordingResponse(BaseModel):
    tipo: str = "recording_started"
    estado: RecordingStatusResponse


class StopRecordingRequest(BaseModel):
    guardar_audio: bool = True
    incluir_samples: bool = True
    max_points: int = Field(2000, ge=2, le=20000)


class StopRecordingResponse(BaseModel):
    tipo: str = "recording_stopped"
    estado: RecordingStatusResponse
    grabacion: ResumenAudio


class UploadRecordingResponse(BaseModel):
    tipo: str = "uploaded_recording"
    nombre_archivo: str
    content_type: str
    audio_path: str
    audio_url: str
    tamano_bytes: int


class StoredAudioSamplesResponse(ResumenAudio):
    pass


class PinkNoiseAudioRequest(BaseModel):
    duracion: float = Field(5.0, gt=0, le=300)
    fs: SampleRateHz = SampleRateHz.HZ_44100


class SineSweepAudioRequest(BaseModel):
    frecuencia_inicial: float = Field(20.0, gt=0, le=20000)
    frecuencia_final: float = Field(20000.0, gt=0, le=96000)
    duracion: float = Field(5.0, gt=0, le=300)
    fs: SampleRateHz = SampleRateHz.HZ_44100
    tipo_barrido: TipoBarrido = TipoBarrido.LOGARITMICO


class AudioSamplesResponse(BaseModel):
    fs: int
    duracion: float
    n_canales: int
    samples_reducidos: bool
    amplitude: list[float] | None = None
    channels: list[list[float]] | None = None


__all__ = [
    "AudioSamplesResponse",
    "DeviceInfoResponse",
    "PinkNoiseAudioRequest",
    "PinkNoiseRequest",
    "PinkNoiseResponse",
    "RecordingStatusResponse",
    "ResumenAudio",
    "SampleRateHz",
    "SineSweepAudioRequest",
    "SineSweepRequest",
    "SineSweepResponse",
    "StartRecordingRequest",
    "StartRecordingResponse",
    "StoredAudioSamplesResponse",
    "StopRecordingRequest",
    "StopRecordingResponse",
    "TipoBarrido",
    "UploadRecordingResponse",
]
