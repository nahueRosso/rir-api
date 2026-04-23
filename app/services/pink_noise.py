"""Servicio de generacion de ruido rosa.

Milestone 1: Generacion de senales.
"""

import numpy as np


def generar_ruido_rosa(duracion: float, fs: int) -> np.ndarray:
    """Genera una senal de ruido rosa de la duracion especificada.

    El ruido rosa tiene una densidad espectral de potencia inversamente
    proporcional a la frecuencia (1/f). Esto significa que cada octava
    contiene la misma cantidad de energia, lo cual lo hace util para
    mediciones acusticas.

    Algoritmo sugerido:
    1. Generar ruido blanco (distribucion normal) de la duracion deseada.
    2. Aplicar la transformada de Fourier (np.fft.rfft).
    3. Crear un vector de frecuencias correspondiente.
    4. Dividir cada componente por sqrt(f) (omitir f=0 para evitar division por cero).
    5. Aplicar la transformada inversa (np.fft.irfft).
    6. Normalizar la senal resultante al rango [-1, 1].

    Parameters
    ----------
    duracion : float
        Duracion de la senal en segundos.
    fs : int
        Frecuencia de muestreo en Hz.

    Returns
    -------
    np.ndarray
        Senal de ruido rosa normalizada, de longitud ``int(duracion * fs)``.
    """
    raise NotImplementedError("Implementar en Milestone 1")
