from __future__ import annotations

from pydantic import BaseModel, Field


class SmoothingResponse(BaseModel):
    fs: int
    ventana: str
    tiempo: list[float]
    envolvente: list[float]


class SchroederResponse(BaseModel):
    fs: int
    tiempo: list[float]
    edc_db: list[float]


class LinearRegressionRequest(BaseModel):
    x: list[float] = Field(..., min_length=2, description="Variable independiente (p.ej. tiempo)")
    y: list[float] = Field(..., min_length=2, description="Variable dependiente (p.ej. EDC en dB)")


class LinearRegressionResponse(BaseModel):
    pendiente: float
    ordenada_al_origen: float
    r_cuadrado: float


class AcousticParametersResponse(BaseModel):
    fs: int
    # Un valor es None cuando la RI no tiene suficiente rango de decaimiento
    # en esa banda para ajustar la regresion (NaN en el calculo interno).
    parametros: dict[str, dict[str, float | None]]


class LundebyResponse(BaseModel):
    fs: int
    indice_truncamiento: int
    tiempo_truncamiento: float
    nivel_ruido_db: float


__all__ = [
    "AcousticParametersResponse",
    "LinearRegressionRequest",
    "LinearRegressionResponse",
    "LundebyResponse",
    "SchroederResponse",
    "SmoothingResponse",
]
