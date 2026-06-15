"""Servicio de calculo de parametros acusticos segun ISO 3382.

Milestone 3: Analisis de parametros acusticos.
"""

import numpy as np


def suavizar_signal(signal: np.ndarray, ventana: int) -> np.ndarray:
    """Aplica un suavizado por media movil a la senal.

    Parameters
    ----------
    signal : np.ndarray
        Senal de entrada (array 1D).
    ventana : int
        Tamano de la ventana de suavizado en muestras.

    Returns
    -------
    np.ndarray
        Senal suavizada, de la misma longitud que ``signal``.
    """
    raise NotImplementedError("Implementar en Milestone 3")


def integral_schroeder(ri: np.ndarray) -> np.ndarray:
    """Calcula la integral de Schroeder (Energy Decay Curve).

    Parameters
    ----------
    ri : np.ndarray
        Respuesta al impulso (array 1D).

    Returns
    -------
    np.ndarray
        Curva de decaimiento energetico (EDC), normalizada.

    References
    ----------
    .. [1] Schroeder, M. R. (1965). "New method of measuring reverberation
       time." The Journal of the Acoustical Society of America.
    """
    ri_array = np.asarray(ri, dtype=np.float64)
    if ri_array.ndim != 1:
        raise ValueError("ri debe ser un array 1D")
    if ri_array.size == 0:
        raise ValueError("ri no puede estar vacia")

    energia = ri_array**2
    edc = np.cumsum(energia[::-1])[::-1]
    if edc[0] > 0.0:
        edc = edc / edc[0]
    return edc


def regresion_lineal(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Calcula la regresion lineal por minimos cuadrados.

    Parameters
    ----------
    x : np.ndarray
        Variable independiente (array 1D).
    y : np.ndarray
        Variable dependiente (array 1D).

    Returns
    -------
    pendiente : float
        Pendiente de la recta ajustada (m).
    ordenada : float
        Ordenada al origen de la recta ajustada (b).
    """
    x_array = np.asarray(x, dtype=np.float64)
    y_array = np.asarray(y, dtype=np.float64)

    if x_array.ndim != 1 or y_array.ndim != 1:
        raise ValueError("x e y deben ser arrays 1D")
    if x_array.size != y_array.size:
        raise ValueError("x e y deben tener la misma longitud")
    if x_array.size < 2:
        raise ValueError("se requieren al menos dos muestras")

    pendiente, ordenada = np.polyfit(x_array, y_array, deg=1)
    return float(pendiente), float(ordenada)


def calcular_parametros_acusticos(ri: np.ndarray, fs: int) -> dict:
    """Calcula los parametros acusticos de una sala a partir de su RI.

    Parameters
    ----------
    ri : np.ndarray
        Respuesta al impulso (array 1D).
    fs : int
        Frecuencia de muestreo en Hz.

    Returns
    -------
    dict
        Diccionario con los parametros acusticos por banda.

    References
    ----------
    .. [1] ISO 3382-1:2009. "Acoustics -- Measurement of room acoustic
       parameters -- Part 1: Performance spaces."
    """
    raise NotImplementedError("Implementar en Milestone 3")


def metodo_lundeby(ri: np.ndarray, fs: int) -> int:
    """Estima el punto de truncamiento de la RI (metodo de Lundeby).

    Parameters
    ----------
    ri : np.ndarray
        Respuesta al impulso (array 1D).
    fs : int
        Frecuencia de muestreo en Hz.

    Returns
    -------
    int
        Indice de la muestra donde se estima el punto de truncamiento.

    Notes
    -----
    Esta funcion es **opcional** (extra credit).

    References
    ----------
    .. [1] Lundeby, A. et al. (1995). "Uncertainties of measurements in
       room acoustics." Acta Acustica.
    """
    raise NotImplementedError("Implementar en Milestone 3 (opcional)")
