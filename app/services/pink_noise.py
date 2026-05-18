"""Servicio de generacion de ruido rosa.

Milestone 1: Generacion de senales.
"""

import numpy as np


def generar_ruido_rosa(duracion: float, fs: int) -> np.ndarray:
    """Genera ruido rosa aproximado mediante filtrado espectral 1/sqrt(f)."""
    if duracion <= 0:
        raise ValueError("duracion debe ser positiva")
    if fs <= 0:
        raise ValueError("fs debe ser positivo")

    n_samples = int(duracion * fs)
    if n_samples <= 0:
        raise ValueError("duracion * fs debe generar al menos una muestra")

    ruido_blanco = np.random.randn(n_samples)
    espectro = np.fft.rfft(ruido_blanco)
    freqs = np.fft.rfftfreq(n_samples, d=1 / fs)

    filtro = np.ones_like(freqs)
    filtro[1:] = 1 / np.sqrt(freqs[1:])

    espectro_rosa = espectro * filtro
    ruido_rosa = np.fft.irfft(espectro_rosa, n=n_samples)

    max_abs = np.max(np.abs(ruido_rosa))
    if max_abs > 0:
        ruido_rosa = ruido_rosa / max_abs

    return ruido_rosa.astype(np.float32)
