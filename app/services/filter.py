"""Servicio de filtrado por bandas de octava.

Milestone 2: Procesamiento de la respuesta al impulso.
"""

import numpy as np


def filtro_octava(
    signal: np.ndarray, fc: float, fs: int, orden: int = 4
) -> np.ndarray:
    """Aplica un filtro pasabanda de una octava centrado en ``fc``.

    Implementa un filtro Butterworth pasabanda cuyas frecuencias de corte
    corresponden a los limites de una banda de octava segun IEC 61260:
    - Frecuencia inferior: ``fc / sqrt(2)``
    - Frecuencia superior: ``fc * sqrt(2)``

    Parameters
    ----------
    signal : np.ndarray
        Senal de entrada (array 1D).
    fc : float
        Frecuencia central de la banda de octava en Hz.
    fs : int
        Frecuencia de muestreo en Hz.
    orden : int, optional
        Orden del filtro Butterworth (por defecto 4).

    Returns
    -------
    np.ndarray
        Senal filtrada (array 1D).
    """
    raise NotImplementedError("Implementar en Milestone 2")
