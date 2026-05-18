from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf


def device() -> dict[str, Any]:
    default_input, default_output = sd.default.device
    dispositivos = sd.query_devices()
    return {
        "default_input_device": _to_builtin(default_input),
        "default_output_device": _to_builtin(default_output),
        "devices": [_to_builtin(dict(dispositivo)) for dispositivo in dispositivos],
    }


def divice() -> dict[str, Any]:
    return device()


def guardar_audio(signal: np.ndarray, fs: int, nombre_archivo: str = "grabacion.wav") -> Path:
    """Guarda un archivo de audio dentro de ``data/`` en la raiz del repositorio."""
    signal_array = np.asarray(signal, dtype=np.float32)

    if signal_array.ndim not in (1, 2):
        raise ValueError("signal debe ser un array 1D (mono) o 2D (multicanal)")
    if signal_array.size == 0:
        raise ValueError("signal no puede estar vacia")
    if fs <= 0:
        raise ValueError("fs debe ser un entero positivo")
    if not nombre_archivo:
        raise ValueError("nombre_archivo no puede estar vacio")

    repo_root = obtener_repo_root()

    ruta_salida = repo_root / "data" / nombre_archivo
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(ruta_salida), signal_array, fs)
    return ruta_salida


def obtener_repo_root() -> Path:
    repo_root = Path.cwd()
    if not (repo_root / "pyproject.toml").exists():
        candidatos = [repo_root, *repo_root.parents]
        repo_root = next(
            (path for path in candidatos if (path / "pyproject.toml").exists()),
            repo_root,
        )
    return repo_root


def obtener_ruta_audio(nombre_archivo: str) -> Path:
    if not nombre_archivo or Path(nombre_archivo).name != nombre_archivo:
        raise ValueError("nombre_archivo invalido")
    return obtener_repo_root() / "data" / nombre_archivo


def reproducir_y_grabar(signal: np.ndarray, fs: int, duracion_grabacion: float) -> np.ndarray:
    """
    Reproduce una señal de audio y graba la entrada simultáneamente.

    La función agrega un silencio inicial (pre-roll) de 0.5 segundos al principio
    de la señal para compensar la latencia del sistema de audio. Si la señal
    de entrada es mono (1D), la grabación devuelta también será mono (1D).

    Parameters
    ----------
    signal : np.ndarray
        Señal a reproducir. Puede ser un array 1D (mono) o 2D con forma
        (muestras, canales).
    fs : int
        Frecuencia de muestreo en Hz. Debe ser mayor que cero.
    duracion_grabacion : float
        Duración total de la grabación en segundos. Debe ser mayor o igual
        a la duración de la señal reproducida.

    Returns
    -------
    np.ndarray
        Array de tipo np.float32 con la señal grabada. Mantiene la misma
        estructura de canales (1D o 2D) que la señal de entrada.

    Raises
    ------
    ValueError
        Si la señal tiene una dimensión inválida, está vacía, fs o
        duracion_grabacion no son positivos, o si la duración de la grabación
        es menor que la duración de la señal.
    RuntimeError
        Si ocurre un error de PortAudio, si los dispositivos de audio no están
        disponibles o si falla la configuración de canales/frecuencia.
    """
    signal_array = np.asarray(signal, dtype=np.float32)

    if signal_array.ndim not in (1, 2):
        raise ValueError("signal debe ser un array 1D (mono) o 2D (multicanal)")
    if signal_array.size == 0:
        raise ValueError("signal no puede estar vacia")
    if fs <= 0:
        raise ValueError("fs debe ser un entero positivo")
    if duracion_grabacion <= 0:
        raise ValueError("duracion_grabacion debe ser positiva")

    is_mono = signal_array.ndim == 1
    signal_2d = signal_array[:, np.newaxis] if is_mono else signal_array

    duracion_signal = signal_2d.shape[0] / fs
    if duracion_grabacion < duracion_signal:
        raise ValueError("duracion_grabacion debe ser mayor o igual a la duracion de la senal")

    channels = signal_2d.shape[1]
    preroll_samples = int(round(0.5 * fs))
    total_samples = int(round(duracion_grabacion * fs))

    salida = np.zeros((total_samples, channels), dtype=np.float32)
    inicio = min(preroll_samples, total_samples)
    samples_to_copy = min(signal_2d.shape[0], total_samples - inicio)
    if samples_to_copy > 0:
        salida[inicio : inicio + samples_to_copy] = signal_2d[:samples_to_copy]

    try:
        sd.check_input_settings(samplerate=fs, channels=channels, dtype="float32")
        sd.check_output_settings(samplerate=fs, channels=channels, dtype="float32")
        print(
            f"Reproduciendo y grabando {duracion_grabacion:.2f} s "
            f"a {fs} Hz con {channels} canal(es)..."
        )
        grabacion = sd.playrec(
            salida,
            samplerate=fs,
            channels=channels,
            dtype="float32",
            blocking=True,
        )
    except sd.PortAudioError as exc:
        raise RuntimeError(f"No fue posible acceder a los dispositivos de audio: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Error durante la reproduccion y grabacion de audio: {exc}") from exc

    grabacion_array = np.asarray(grabacion, dtype=np.float32)
    if is_mono:
        return grabacion_array[:, 0]
    return grabacion_array


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_builtin(item) for item in value)
    if isinstance(value, np.generic):
        return value.item()
    return value
