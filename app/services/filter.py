"""Servicio de filtrado por bandas de octava (IEC 61260)."""

import numpy as np
from scipy import signal as sig


def filtro_octava_crudo(senal: np.ndarray, fc: float, fs: int, orden: int = 4) -> np.ndarray:
    """Aplica un filtro pasabanda de una octava centrado en ``fc`` (IEC 61260)
    y devuelve la senal filtrada tal cual, sin envolvente ni suavizado.

    Frecuencias de corte segun IEC 61260:
        f_inf = fc / sqrt(2),  f_sup = fc * sqrt(2)

    Esta es la base correcta para integrar energia ($h^2(t)$) en calculos
    como Schroeder, D50 o C80: cualquier suavizado adicional (p.ej. una
    envolvente de Hilbert) distorsiona la distribucion temporal de energia
    justo en los limites de ventana (50/80 ms) que esos parametros necesitan.

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
        Senal filtrada (float64, misma longitud que la entrada, fase cero).

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

    # Second-order sections (sos): el diseño clasico b,a de scipy.signal.butter
    # pierde precision y puede dar NaN/Inf en bandas muy angostas respecto a
    # Nyquist (p.ej. 125 Hz a fs=44100 Hz). sosfiltfilt es numericamente
    # estable para ese mismo caso.
    sos = sig.butter(orden, [w_inf, w_sup], btype="band", output="sos")
    return sig.sosfiltfilt(sos, np.asarray(senal, dtype=np.float64))
