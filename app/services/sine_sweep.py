"""Servicio de generacion de sine sweep."""

from __future__ import annotations

import numpy as np


def generar_sine_sweep(
    f1: float,
    f2: float,
    duracion: float,
    fs: int,
    tipo_barrido: str = "logaritmico",
) -> tuple[np.ndarray, np.ndarray]:
    """Genera un barrido senoidal y su filtro inverso, ambos normalizados."""
    if f1 <= 0 or f2 <= 0:
        raise ValueError("las frecuencias deben ser positivas")
    if f2 <= f1:
        raise ValueError("frecuencia_final debe ser mayor que frecuencia_inicial")
    if duracion <= 0:
        raise ValueError("duracion debe ser positiva")
    if fs <= 0:
        raise ValueError("fs debe ser positivo")
    if f2 >= fs / 2:
        raise ValueError("frecuencia_final debe ser menor a la frecuencia de Nyquist")
    if tipo_barrido not in {"lineal", "logaritmico"}:
        raise ValueError("tipo_barrido debe ser 'lineal' o 'logaritmico'")

    muestras = int(duracion * fs)
    if muestras <= 0:
        raise ValueError("duracion * fs debe generar al menos una muestra")

    t = np.arange(muestras, dtype=np.float64) / fs

    if tipo_barrido == "lineal":
        k = (f2 - f1) / duracion
        fase = 2 * np.pi * (f1 * t + 0.5 * k * t**2)
        sweep = np.sin(fase)
        filtro_inverso = sweep[::-1]
    else:
        w1 = 2 * np.pi * f1
        w2 = 2 * np.pi * f2
        tasa = np.log(w2 / w1)
        fase = (w1 * duracion / tasa) * (np.exp((t / duracion) * tasa) - 1)
        sweep = np.sin(fase)
        envolvente = np.exp((-t / duracion) * tasa)
        filtro_inverso = sweep[::-1] * envolvente

    sweep_norm = _normalizar_audio(sweep)
    filtro_inverso_norm = _normalizar_audio(filtro_inverso)
    return sweep_norm, filtro_inverso_norm


def _normalizar_audio(signal: np.ndarray) -> np.ndarray:
    max_abs = np.max(np.abs(signal))
    if max_abs <= 0:
        return signal.astype(np.float32)
    return (signal / max_abs).astype(np.float32)
