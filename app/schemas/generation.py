from __future__ import annotations

from enum import Enum, IntEnum
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


class TipoBarrido(str, Enum):
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


class PlayRecordRequest(BaseModel):
    signal: list[float] | list[list[float]]
    fs: SampleRateHz
    duracion_grabacion: float = Field(..., gt=0)
    guardar_audio: bool = True
    nombre_archivo: str = "grabacion.wav"
    incluir_samples: bool = True
    max_points: int = Field(2000, ge=2, le=20000)


class PlayRecordResponse(BaseModel):
    tipo: str = "play_record"
    fs: int
    duracion_grabacion: float
    senal_entrada: ResumenAudio
    grabacion: ResumenAudio


class StoredAudioSamplesResponse(ResumenAudio):
    pass


__all__ = [
    "DeviceInfoResponse",
    "PinkNoiseRequest",
    "PinkNoiseResponse",
    "PlayRecordRequest",
    "PlayRecordResponse",
    "ResumenAudio",
    "SampleRateHz",
    "SineSweepRequest",
    "SineSweepResponse",
    "StoredAudioSamplesResponse",
    "TipoBarrido",
]
