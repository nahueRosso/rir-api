from __future__ import annotations

from pydantic import BaseModel, Field


class SynthesizeRiRequest(BaseModel):
    t60_por_banda: dict[str, float] = Field(
        default={
            "125": 2.0,
            "250": 1.8,
            "500": 1.5,
            "1000": 1.2,
            "2000": 1.0,
            "4000": 0.8,
        },
        description="Frecuencia central (Hz) como clave string : T60 en segundos.",
    )
    fs: int = Field(44100, gt=0)
    duracion: float = Field(3.0, gt=0, le=30)


class LogScaleResponse(BaseModel):
    fs: int
    duracion: float
    n_muestras: int
    tiempo: list[float]
    db: list[float]


__all__ = ["LogScaleResponse", "SynthesizeRiRequest"]
