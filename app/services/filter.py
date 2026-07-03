"""Servicio de filtrado por bandas de octava (IEC 61260)."""

import numpy as np
from scipy import signal as sig
from scipy.signal import hilbert

# Ventana de suavizado en muestras (~10 ms a 44100 Hz).
_VENTANA_SUAVIZADO = 441


def filtro_octava(senal: np.ndarray, fc: float, fs: int, orden: int = 4) -> np.ndarray:
    """Aplica un filtro pasabanda de una octava centrado en ``fc`` y retorna
    la envolvente de amplitud (magnitud de la senal analitica) suavizada.

    Frecuencias de corte segun IEC 61260:
        f_inf = fc / sqrt(2),  f_sup = fc * sqrt(2)

    El uso de la envolvente elimina los cruces por cero de la senal
    filtrada, permitiendo medir la curva de decaimiento energetico
    directamente sobre la salida al cuadrado.

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
        Envolvente de la senal filtrada (float32, misma longitud que la entrada).

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

    w_inf = f_inf / nyq
    w_sup = f_sup / nyq

    b, a = sig.butter(orden, [w_inf, w_sup], btype="band")
    filtrada = sig.filtfilt(b, a, np.asarray(senal, dtype=np.float64))

    # Envolvente de amplitud via transformada de Hilbert
    envolvente = np.abs(hilbert(filtrada))

    # Suavizado por media movil para estabilizar la curva
    ventana = min(_VENTANA_SUAVIZADO, len(envolvente))
    kernel = np.ones(ventana, dtype=np.float64) / ventana
    envolvente_suavizada = np.convolve(envolvente, kernel, mode="same")

    return envolvente_suavizada.astype(np.float32)
