"""Servicio de calculo de parametros acusticos segun ISO 3382.

Milestone 3: Analisis de parametros acusticos.
"""

import numpy as np
from scipy.signal import hilbert

from app.services.filter import filtro_octava

_EPS = 1e-12
_BANDAS_OCTAVA = (125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0)


def suavizar_signal(signal: np.ndarray, ventana: int | str = "hilbert") -> np.ndarray:
    """Suaviza una senal para reducir fluctuaciones del ruido.

    Parameters
    ----------
    signal : np.ndarray
        Senal de entrada (tipicamente una RI filtrada por banda).
    ventana : int | str
        Si es int: tamano de la ventana para media movil de energia (en muestras).
        Si es 'hilbert' (default): usa la envolvente de Hilbert.

    Returns
    -------
    np.ndarray
        Senal suavizada (envolvente de energia), misma longitud que ``signal``.
    """
    arr = np.asarray(signal, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("signal debe ser un array 1D")
    if arr.size == 0:
        raise ValueError("signal no puede estar vacia")

    if isinstance(ventana, str):
        if ventana != "hilbert":
            raise ValueError(f"ventana de texto no soportada: {ventana!r} (usar 'hilbert')")
        return np.abs(hilbert(arr))

    ventana_int = int(ventana)
    if ventana_int < 1:
        raise ValueError("ventana debe ser un entero >= 1")

    energia = arr**2
    kernel = np.ones(ventana_int, dtype=np.float64) / ventana_int
    return np.convolve(energia, kernel, mode="same")


def integral_schroeder(ri: np.ndarray) -> np.ndarray:
    """Calcula la integral de Schroeder (Energy Decay Curve).

    Parameters
    ----------
    ri : np.ndarray
        Respuesta al impulso (array 1D).

    Returns
    -------
    np.ndarray
        Curva de decaimiento en dB, normalizada a 0 dB en el primer punto.

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
    integral_inversa = np.cumsum(energia[::-1])[::-1]
    referencia = integral_inversa[0] if integral_inversa[0] > 0.0 else _EPS
    return 10.0 * np.log10(integral_inversa / referencia + _EPS)


def regresion_lineal(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Calcula la regresion lineal por minimos cuadrados.

    Parameters
    ----------
    x : np.ndarray
        Variable independiente (tipicamente tiempo en segundos).
    y : np.ndarray
        Variable dependiente (tipicamente curva de Schroeder en dB).

    Returns
    -------
    tuple[float, float, float]
        (pendiente, ordenada_al_origen, r_cuadrado).
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

    y_pred = pendiente * x_array + ordenada
    ss_res = np.sum((y_array - y_pred) ** 2)
    ss_tot = np.sum((y_array - np.mean(y_array)) ** 2)
    r_cuadrado = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0

    return float(pendiente), float(ordenada), float(r_cuadrado)


def _segmento_decaimiento(
    tiempo: np.ndarray, edc_db: np.ndarray, db_inicio: float, db_fin: float
) -> tuple[np.ndarray, np.ndarray] | None:
    """Extrae los puntos de la EDC entre ``db_inicio`` y ``db_fin`` (db_fin < db_inicio)."""
    mascara = (edc_db <= db_inicio) & (edc_db >= db_fin)
    indices = np.flatnonzero(mascara)
    if indices.size < 2:
        return None
    return tiempo[indices], edc_db[indices]


def _tiempo_reverberacion(
    tiempo: np.ndarray, edc_db: np.ndarray, db_inicio: float, db_fin: float
) -> float:
    """Regresion sobre el tramo [db_inicio, db_fin] de la EDC, extrapolada a -60 dB."""
    segmento = _segmento_decaimiento(tiempo, edc_db, db_inicio, db_fin)
    if segmento is None:
        return float("nan")
    t_seg, y_seg = segmento
    pendiente, _, _ = regresion_lineal(t_seg, y_seg)
    if pendiente >= 0.0:
        return float("nan")
    return -60.0 / pendiente


def _clave_banda(fc: float) -> str:
    return str(int(fc)) if float(fc).is_integer() else str(fc)


def calcular_parametros_acusticos(ri: np.ndarray, fs: int) -> dict[str, dict[str, float]]:
    """Calcula los parametros acusticos ISO 3382 por banda de octava.

    Parameters
    ----------
    ri : np.ndarray
        Respuesta al impulso.
    fs : int
        Frecuencia de muestreo en Hz.

    Returns
    -------
    dict[str, dict[str, float]]
        Estructura: {parametro: {frecuencia_central: valor}}.
        Parametros: EDT, T10, T20, T30, T60, D50, C80.
        Las bandas no realizables para el ``fs`` dado se omiten.

    References
    ----------
    .. [1] ISO 3382-1:2009. "Acoustics -- Measurement of room acoustic
       parameters -- Part 1: Performance spaces."
    """
    ri_array = np.asarray(ri, dtype=np.float64)
    if ri_array.ndim != 1:
        raise ValueError("ri debe ser un array 1D")
    if ri_array.size == 0:
        raise ValueError("ri no puede estar vacia")

    parametros: dict[str, dict[str, float]] = {
        "EDT": {},
        "T10": {},
        "T20": {},
        "T30": {},
        "T60": {},
        "D50": {},
        "C80": {},
    }

    for fc in _BANDAS_OCTAVA:
        try:
            banda = filtro_octava(ri_array, fc, fs)
        except ValueError:
            continue

        edc_db = integral_schroeder(banda)
        tiempo = np.arange(len(edc_db)) / fs

        edt = _tiempo_reverberacion(tiempo, edc_db, 0.0, -10.0)
        t10 = _tiempo_reverberacion(tiempo, edc_db, -5.0, -15.0)
        t20 = _tiempo_reverberacion(tiempo, edc_db, -5.0, -25.0)
        t30 = _tiempo_reverberacion(tiempo, edc_db, -5.0, -35.0)
        t60 = t30 if not np.isnan(t30) else t20

        energia_banda = banda.astype(np.float64) ** 2
        energia_total = np.sum(energia_banda)
        n50 = min(int(0.050 * fs), len(energia_banda))
        n80 = min(int(0.080 * fs), len(energia_banda))

        d50 = float(np.sum(energia_banda[:n50]) / (energia_total + _EPS) * 100.0)
        energia_temprana = np.sum(energia_banda[:n80])
        energia_tardia = np.sum(energia_banda[n80:])
        c80 = float(10.0 * np.log10((energia_temprana + _EPS) / (energia_tardia + _EPS)))

        clave = _clave_banda(fc)
        parametros["EDT"][clave] = edt
        parametros["T10"][clave] = t10
        parametros["T20"][clave] = t20
        parametros["T30"][clave] = t30
        parametros["T60"][clave] = t60
        parametros["D50"][clave] = d50
        parametros["C80"][clave] = c80

    return parametros


def metodo_lundeby(ri: np.ndarray, fs: int) -> tuple[int, float]:
    """Determina el punto de truncamiento de la RI usando el metodo de Lundeby.

    Parameters
    ----------
    ri : np.ndarray
        Respuesta al impulso.
    fs : int
        Frecuencia de muestreo en Hz.

    Returns
    -------
    tuple[int, float]
        (indice_truncamiento, nivel_ruido_dB).

    Notes
    -----
    Esta funcion es **opcional** (extra credit).

    References
    ----------
    .. [1] Lundeby, A. et al. (1995). "Uncertainties of measurements in
       room acoustics." Acta Acustica.
    """
    ri_array = np.asarray(ri, dtype=np.float64)
    if ri_array.ndim != 1:
        raise ValueError("ri debe ser un array 1D")

    energia = ri_array**2
    n = len(energia)

    intervalo = max(1, int(0.01 * fs))  # bloques de ~10 ms
    n_bloques = n // intervalo
    if n_bloques < 3:
        raise ValueError("senal demasiado corta para el metodo de Lundeby")

    bloques = energia[: n_bloques * intervalo].reshape(n_bloques, intervalo).mean(axis=1)
    tiempo_bloques = (np.arange(n_bloques) + 0.5) * intervalo / fs

    referencia = np.max(bloques) if np.max(bloques) > 0.0 else _EPS
    curva_db = 10.0 * np.log10(bloques / referencia + _EPS)

    n_ruido = max(1, int(0.1 * n_bloques))
    ruido_db = float(np.mean(curva_db[-n_ruido:]))

    max_idx = int(np.argmax(curva_db))
    umbral = ruido_db + 10.0
    candidatos = np.flatnonzero(curva_db[max_idx:] <= umbral)
    cruce_idx = max_idx + int(candidatos[0]) if candidatos.size else n_bloques - 1

    for _ in range(5):
        if cruce_idx - max_idx < 2:
            break

        pendiente, ordenada, _ = regresion_lineal(
            tiempo_bloques[max_idx:cruce_idx], curva_db[max_idx:cruce_idx]
        )
        if pendiente >= 0.0:
            break

        cola_inicio = min(cruce_idx, n_bloques - 1)
        n_ruido_cola = max(1, int(0.1 * (n_bloques - cola_inicio)))
        cola = curva_db[cola_inicio:] if cola_inicio < n_bloques else curva_db[-n_ruido_cola:]
        if cola.size:
            ruido_db = float(np.mean(cola))

        nuevo_cruce_tiempo = (ruido_db - ordenada) / pendiente
        nuevo_cruce_idx = int(np.searchsorted(tiempo_bloques, nuevo_cruce_tiempo))
        nuevo_cruce_idx = min(max(nuevo_cruce_idx, max_idx + 2), n_bloques - 1)

        if nuevo_cruce_idx == cruce_idx:
            break
        cruce_idx = nuevo_cruce_idx

    indice_muestra = int(cruce_idx * intervalo)
    return indice_muestra, ruido_db
