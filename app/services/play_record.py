from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, Timer
from time import monotonic
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf


def device() -> dict[str, Any]:
    """Retorna informacion de los dispositivos de audio detectados por PortAudio."""
    default_input, default_output = sd.default.device
    dispositivos = sd.query_devices()
    return {
        "default_input_device": _to_builtin(default_input),
        "default_output_device": _to_builtin(default_output),
        "devices": [_to_builtin(dict(dispositivo)) for dispositivo in dispositivos],
    }


def divice() -> dict[str, Any]:
    """Alias legacy de :func:`device` mantenido por compatibilidad."""
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

    ruta_salida = obtener_repo_root() / "data" / nombre_archivo
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(ruta_salida), signal_array, fs)
    return ruta_salida


def obtener_repo_root() -> Path:
    """Ubica la raiz del repositorio buscando ``pyproject.toml`` hacia arriba."""
    repo_root = Path.cwd()
    if not (repo_root / "pyproject.toml").exists():
        candidatos = [repo_root, *repo_root.parents]
        repo_root = next(
            (path for path in candidatos if (path / "pyproject.toml").exists()),
            repo_root,
        )
    return repo_root


def obtener_ruta_audio(nombre_archivo: str) -> Path:
    """Construye una ruta segura dentro de ``data/`` para un nombre de archivo simple."""
    if not nombre_archivo or Path(nombre_archivo).name != nombre_archivo:
        raise ValueError("nombre_archivo invalido")
    return obtener_repo_root() / "data" / nombre_archivo


def guardar_audio_subido(
    contenido: bytes,
    nombre_archivo: str,
) -> Path:
    """Guarda en ``data/`` un archivo binario recibido desde un upload HTTP."""
    if not contenido:
        raise ValueError("el archivo no puede estar vacio")
    ruta_salida = obtener_ruta_audio(nombre_archivo)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_bytes(contenido)
    return ruta_salida


def obtener_media_type_audio(nombre_archivo: str) -> str:
    """Infiere el ``media_type`` HTTP a partir de la extension del archivo."""
    media_type, _ = mimetypes.guess_type(nombre_archivo)
    return media_type or "application/octet-stream"


def reproducir_y_grabar(signal: np.ndarray, fs: int, duracion_grabacion: float) -> np.ndarray:
    """Reproduce una senal y graba simultaneamente en la maquina del backend.

    Agrega un silencio inicial de 0.5 segundos para compensar parte de la
    latencia del sistema de audio.
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
        grabacion = sd.playrec(
            salida,
            samplerate=fs,
            channels=channels,
            dtype="float32",
        )
        sd.wait()
    except Exception as exc:
        raise RuntimeError(f"No fue posible acceder a los dispositivos de audio: {exc}") from exc

    grabacion_array = np.asarray(grabacion, dtype=np.float32)
    if is_mono:
        return grabacion_array[:, 0]
    return grabacion_array


@dataclass
class RecordingSession:
    """Estado compartido de una grabacion manual en curso."""
    stream: sd.InputStream | None = None
    fs: int | None = None
    channels: int | None = None
    input_device: int | None = None
    nombre_archivo: str | None = None
    started_at: float | None = None
    auto_stop_seconds: float | None = None
    auto_stop_timer: Timer | None = None
    frames: list[np.ndarray] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)
    ultimo_archivo_guardado: str | None = None
    ultimo_motivo_fin: str | None = None
    ultima_duracion_grabada: float = 0.0

    def callback(self, indata, frames, time_info, status) -> None:
        """Acumula bloques de audio entrantes del ``InputStream`` activo."""
        _ = frames, time_info
        if status:
            print(f"Estado de grabacion: {status}")
        with self.lock:
            self.frames.append(np.array(indata, dtype=np.float32, copy=True))

    def reset_active(self) -> None:
        """Limpia solo el estado de la grabacion activa y conserva el historico final."""
        self.stream = None
        self.fs = None
        self.channels = None
        self.input_device = None
        self.nombre_archivo = None
        self.started_at = None
        self.auto_stop_seconds = None
        self.auto_stop_timer = None
        self.frames = []


_recording_session = RecordingSession()


def iniciar_grabacion(
    fs: int,
    canales: int = 1,
    input_device: int | None = None,
    nombre_archivo: str = "grabacion_manual.wav",
    auto_stop_seconds: float = 60.0,
) -> dict[str, Any]:
    """Inicia una grabacion manual con corte automatico opcional.

    La captura se realiza en segundo plano con ``sounddevice.InputStream`` y
    queda asociada al estado global del proceso FastAPI.
    """
    if fs <= 0:
        raise ValueError("fs debe ser un entero positivo")
    if canales <= 0:
        raise ValueError("canales debe ser un entero positivo")
    if not nombre_archivo:
        raise ValueError("nombre_archivo no puede estar vacio")
    if auto_stop_seconds <= 0:
        raise ValueError("auto_stop_seconds debe ser positivo")

    with _recording_session.lock:
        if _recording_session.stream is not None:
            raise RuntimeError("ya hay una grabacion en curso")

    try:
        sd.check_input_settings(
            device=input_device,
            samplerate=fs,
            channels=canales,
            dtype="float32",
        )
        stream = sd.InputStream(
            samplerate=fs,
            channels=canales,
            dtype="float32",
            device=input_device,
            callback=_recording_session.callback,
        )
        with _recording_session.lock:
            _recording_session.frames = []
            _recording_session.stream = stream
            _recording_session.fs = fs
            _recording_session.channels = canales
            _recording_session.input_device = input_device
            _recording_session.nombre_archivo = nombre_archivo
            _recording_session.started_at = monotonic()
            _recording_session.auto_stop_seconds = auto_stop_seconds
            _recording_session.ultimo_motivo_fin = None
        stream.start()
        timer = Timer(auto_stop_seconds, _auto_detener_y_guardar_grabacion)
        timer.daemon = True
        with _recording_session.lock:
            _recording_session.auto_stop_timer = timer
        timer.start()
    except sd.PortAudioError as exc:
        _reset_session_after_error()
        raise RuntimeError(
            f"No fue posible acceder al dispositivo de entrada: {exc}"
        ) from exc
    except Exception as exc:
        _reset_session_after_error()
        raise RuntimeError(f"Error al iniciar la grabacion: {exc}") from exc

    return estado_grabacion()


def estado_grabacion() -> dict[str, Any]:
    """Devuelve un snapshot serializable del estado actual de grabacion."""
    recording = _recording_session.stream is not None
    duracion_actual = 0.0
    if recording and _recording_session.started_at is not None:
        duracion_actual = max(0.0, monotonic() - _recording_session.started_at)

    return {
        "recording": recording,
        "fs": _recording_session.fs,
        "canales": _recording_session.channels,
        "input_device": _recording_session.input_device,
        "nombre_archivo": _recording_session.nombre_archivo,
        "duracion_actual": duracion_actual,
        "auto_stop_seconds": _recording_session.auto_stop_seconds,
        "ultimo_archivo_guardado": _recording_session.ultimo_archivo_guardado,
        "ultimo_motivo_fin": _recording_session.ultimo_motivo_fin,
        "ultima_duracion_grabada": _recording_session.ultima_duracion_grabada,
    }


def detener_grabacion(
    guardar_archivo: bool = True,
) -> tuple[np.ndarray, int, Path | None, dict[str, Any]]:
    """Detiene manualmente la grabacion activa y opcionalmente persiste el audio."""
    return _finalizar_grabacion(guardar_archivo=guardar_archivo, motivo_fin="manual")


def _auto_detener_y_guardar_grabacion() -> None:
    """Callback del temporizador que finaliza y guarda la grabacion automaticamente."""
    try:
        _finalizar_grabacion(guardar_archivo=True, motivo_fin="auto_stop")
    except Exception as exc:
        print(f"Error al auto-detener la grabacion: {exc}")


def _finalizar_grabacion(
    guardar_archivo: bool,
    motivo_fin: str,
) -> tuple[np.ndarray, int, Path | None, dict[str, Any]]:
    """Centraliza la finalizacion de la grabacion, el cierre del stream y el guardado."""
    with _recording_session.lock:
        stream = _recording_session.stream
        if stream is None:
            raise RuntimeError("no hay una grabacion en curso")
        fs = _recording_session.fs
        canales = _recording_session.channels
        nombre_archivo = _recording_session.nombre_archivo
        started_at = _recording_session.started_at
        timer = _recording_session.auto_stop_timer
        _recording_session.stream = None
        _recording_session.auto_stop_timer = None

    if timer is not None:
        timer.cancel()

    try:
        stream.stop()
        stream.close()
    except sd.PortAudioError as exc:
        with _recording_session.lock:
            _recording_session.ultimo_motivo_fin = "error_stop"
        raise RuntimeError(f"No fue posible detener la grabacion: {exc}") from exc

    with _recording_session.lock:
        frames = list(_recording_session.frames)

    if fs is None or canales is None or nombre_archivo is None:
        raise RuntimeError("estado de grabacion invalido")
    if not frames:
        with _recording_session.lock:
            _recording_session.reset_active()
            _recording_session.ultimo_motivo_fin = "sin_muestras"
        raise RuntimeError("no se capturaron muestras de audio")

    audio = np.concatenate(frames, axis=0).astype(np.float32, copy=False)
    if canales == 1:
        audio = audio[:, 0]

    ruta = guardar_audio(audio, fs, nombre_archivo) if guardar_archivo else None
    duracion = 0.0
    if started_at is not None:
        duracion = max(0.0, monotonic() - started_at)

    with _recording_session.lock:
        _recording_session.ultimo_archivo_guardado = ruta.name if ruta else None
        _recording_session.ultimo_motivo_fin = motivo_fin
        _recording_session.ultima_duracion_grabada = duracion
        _recording_session.reset_active()

    return audio, fs, ruta, estado_grabacion()


def _reset_session_after_error() -> None:
    """Revierte el estado parcial de una grabacion fallida al iniciar."""
    with _recording_session.lock:
        timer = _recording_session.auto_stop_timer
        _recording_session.reset_active()
    if timer is not None:
        timer.cancel()


def reproducir_audio_guardado(
    nombre_archivo: str,
    output_device: int | None = None,
    blocking: bool = True,
) -> dict[str, Any]:
    """Reproduce un archivo guardado localmente usando el dispositivo de salida indicado."""
    ruta_audio = obtener_ruta_audio(nombre_archivo)
    if not ruta_audio.exists():
        raise FileNotFoundError(nombre_archivo)

    signal, fs = sf.read(str(ruta_audio), dtype="float32", always_2d=False)
    signal_array = np.asarray(signal, dtype=np.float32)
    channels = 1 if signal_array.ndim == 1 else int(signal_array.shape[1])

    try:
        sd.check_output_settings(
            device=output_device,
            samplerate=int(fs),
            channels=channels,
            dtype="float32",
        )
        sd.play(
            signal_array,
            samplerate=int(fs),
            device=output_device,
            blocking=blocking,
        )
    except sd.PortAudioError as exc:
        raise RuntimeError(
            f"No fue posible acceder al dispositivo de salida: {exc}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Error al reproducir el audio: {exc}") from exc

    return {
        "nombre_archivo": ruta_audio.name,
        "output_device": output_device,
        "blocking": blocking,
        "fs": int(fs),
        "cantidad_muestras": int(signal_array.shape[0]),
        "cantidad_canales": channels,
    }


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
