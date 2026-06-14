"""Utilidades de procesamiento de senales (Milestone 2)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve


def cargar_audio(ruta: str | Path) -> tuple[np.ndarray, int]:
    """Carga un archivo de audio WAV o FLAC.

    Parameters
    ----------
    ruta : str | Path
        Ruta al archivo de audio.

    Returns
    -------
    tuple[np.ndarray, int]
        (senal, fs). La senal es float64 normalizada entre -1 y 1.
        Si el archivo es estereo, se devuelve shape (n_muestras, n_canales).

    Raises
    ------
    FileNotFoundError
        Si el archivo no existe.
    ValueError
        Si el formato no es soportado.
    """
    ruta_path = Path(ruta)
    if not ruta_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")

    sufijo = ruta_path.suffix.lower()
    formatos_soportados = {".wav", ".flac", ".ogg", ".aiff", ".aif"}
    if sufijo not in formatos_soportados:
        raise ValueError(
            f"Formato no soportado: '{sufijo}'. "
            f"Formatos validos: {sorted(formatos_soportados)}"
        )

    senal, fs = sf.read(ruta_path, dtype="float64", always_2d=False)
    return np.asarray(senal, dtype=np.float64), int(fs)


def sintetizar_ri(
    t60_por_banda: dict[float, float], fs: int, duracion: float
) -> np.ndarray:
    """Sintetiza una respuesta al impulso con T60 conocidos por banda.

    Modelo: h(t) = n(t) * exp(-alpha * t), donde alpha = 6.908 / T60.
    Suma la contribucion de cada banda de octava filtrada.

    Parameters
    ----------
    t60_por_banda : dict[float, float]
        {frecuencia_central_Hz: T60_segundos}.
        Ejemplo: {125: 2.0, 500: 1.5, 1000: 1.2}.
    fs : int
        Frecuencia de muestreo en Hz.
    duracion : float
        Duracion de la RI en segundos.

    Returns
    -------
    np.ndarray
        RI sintetizada, normalizada, float32.
    """
    from app.services.filter import filtro_octava

    n = int(duracion * fs)
    t = np.arange(n, dtype=np.float64) / fs
    ri = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(seed=42)

    for fc, t60 in t60_por_banda.items():
        if t60 <= 0:
            continue
        alpha = 3.0 * np.log(10.0) / t60  # = 6.908 / T60
        envolvente = np.exp(-alpha * t)
        ruido = rng.standard_normal(n)
        componente = (ruido * envolvente).astype(np.float32)
        try:
            componente = filtro_octava(componente, fc, fs).astype(np.float64)
        except ValueError:
            continue
        ri += componente

    max_val = np.max(np.abs(ri))
    if max_val > 0:
        ri /= max_val

    return ri.astype(np.float32)


def obtener_ri_desde_sweep(
    grabacion: np.ndarray, filtro_inverso: np.ndarray
) -> np.ndarray:
    """Obtiene la respuesta al impulso por deconvolucion.

    h(t) = y(t) * x_inv(t),  donde y es la grabacion y x_inv el filtro inverso.

    Parameters
    ----------
    grabacion : np.ndarray
        Senal grabada (respuesta del recinto al sweep).
    filtro_inverso : np.ndarray
        Filtro inverso del sweep.

    Returns
    -------
    np.ndarray
        RI estimada, normalizada, float32. Comienza en el pico principal.
    """
    grab = np.asarray(grabacion, dtype=np.float64)
    filtro = np.asarray(filtro_inverso, dtype=np.float64)

    # Reducir a mono si alguna señal es multicanal
    if grab.ndim > 1:
        grab = grab.mean(axis=1)
    if filtro.ndim > 1:
        filtro = filtro.mean(axis=1)

    ri = fftconvolve(grab, filtro, mode="full")

    pico_idx = int(np.argmax(np.abs(ri)))

    # Conservar hasta 10 ms antes del pico para capturar la llegada directa
    preroll = min(pico_idx, max(1, int(0.01 * len(grab))))
    ri = ri[pico_idx - preroll :]

    max_val = np.max(np.abs(ri))
    if max_val > 0:
        ri /= max_val

    return ri.astype(np.float32)


def a_escala_log(senal: np.ndarray) -> np.ndarray:
    """Convierte una senal a escala logaritmica (dB) normalizada a 0 dB.

    L(t) = 20 * log10(|h(t)| / max(|h(t)|))

    Parameters
    ----------
    senal : np.ndarray
        Senal de entrada.

    Returns
    -------
    np.ndarray
        Senal en dB (float64). Maximo = 0 dB; piso = -120 dB.

    Raises
    ------
    ValueError
        Si la senal esta vacia o es todo cero.
    """
    arr = np.asarray(senal, dtype=np.float64)
    if arr.size == 0:
        raise ValueError("La senal no puede estar vacia")

    magnitud = np.abs(arr)
    ref = np.max(magnitud)
    if ref <= 0.0:
        raise ValueError("La senal es todo cero: no se puede convertir a dB")

    # Piso de -120 dB para evitar -inf
    piso_lineal = ref * 10.0 ** (-120.0 / 20.0)
    return 20.0 * np.log10(np.maximum(magnitud, piso_lineal) / ref)
