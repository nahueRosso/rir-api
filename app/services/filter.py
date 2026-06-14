"""Servicio de filtrado por bandas de octava (IEC 61260)."""

import numpy as np
from scipy import signal as sig


def filtro_octava(senal: np.ndarray, fc: float, fs: int, orden: int = 4) -> np.ndarray:
    """Aplica un filtro pasabanda de una octava centrado en ``fc``.

    Frecuencias de corte segun IEC 61260:
        f_inf = fc / sqrt(2),  f_sup = fc * sqrt(2)

    Parameters
    ----------
    senal : np.ndarray
        Senal de entrada (array 1D, float).
    fc : float
        Frecuencia central de la banda en Hz.
    fs : int
        Frecuencia de muestreo en Hz.
    orden : int, optional
        Orden del filtro Butterworth (default 4).

    Returns
    -------
    np.ndarray
        Senal filtrada (float32, misma longitud que la entrada).

    Raises
    ------
    ValueError
        Si la banda no es realizable para el fs dado.
    """
    f_inf = fc / np.sqrt(2)
    f_sup = fc * np.sqrt(2)
    nyq = fs / 2.0

    if f_inf <= 0:
        raise ValueError(f"Frecuencia inferior {f_inf:.2f} Hz debe ser positiva")
    if f_sup >= nyq:
        raise ValueError(
            f"Frecuencia superior {f_sup:.1f} Hz supera Nyquist {nyq:.1f} Hz "
            f"(fc={fc} Hz, fs={fs} Hz)"
        )

    W_inf = f_inf / nyq
    W_sup = f_sup / nyq

    b, a = sig.butter(orden, [W_inf, W_sup], btype="band")
    filtrada = sig.filtfilt(b, a, np.asarray(senal, dtype=np.float64))
    return filtrada.astype(np.float32)
