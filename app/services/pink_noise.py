"""Servicio de generacion de ruido rosa.

Milestone 1: Generacion de senales.
"""

import numpy as np


def generar_ruido_rosa(duracion: float, fs: int) -> np.ndarray:
    """
    Genera ruido rosa utilizando el método de filtrado en el dominio frecuencial 1/sqrt(f).

    La señal se genera creando ruido blanco en el dominio del tiempo,
    transformándolo al dominio de la frecuencia mediante la FFT, y aplicando
    un filtro con una respuesta inversamente proporcional a la raíz de la frecuencia
    (1/sqrt(f)). Esto garantiza la caída característica de -3 dB/octava.
    Finalmente, la señal se normaliza para que su valor pico sea 1 o -1.

    Parameters
    ----------
    duracion : float
        Duración de la señal de ruido rosa en segundos. Debe ser mayor que cero.
    fs : int
        Frecuencia de muestreo en Hz. Debe ser mayor que cero.

    Returns
    -------
    np.ndarray
        Array de una dimensión (tipo np.float32) con la señal de ruido rosa
        normalizada entre -1 y 1.

    Raises
    ------
    ValueError
        Si 'duracion' o 'fs' son menores o iguales a cero, o si el producto
        de ambos no genera al menos una muestra.
    """
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
