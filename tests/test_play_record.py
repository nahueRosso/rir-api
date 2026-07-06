"""Tests para app/services/play_record.py mas alla de generar/reproducir (Milestone 1).

Cubre: informacion de dispositivos, gestion de archivos en data/, y el
subsistema de grabacion manual con estado (iniciar/detener/auto-stop),
que no estaba cubierto por tests/test_generacion.py.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.services import play_record


class FakeInputStream:
    """Doble de prueba de ``sounddevice.InputStream`` sin acceso a hardware real."""

    instances: list["FakeInputStream"] = []

    def __init__(self, **kwargs):
        self.callback = kwargs.get("callback")
        self.started = False
        self.stopped = False
        self.closed = False
        self.raise_on_stop = False
        FakeInputStream.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True
        if self.raise_on_stop:
            raise play_record.sd.PortAudioError("fallo simulado al detener")

    def close(self) -> None:
        self.closed = True


class RaisingInputStream:
    """Doble que falla al construirse, para simular un error generico al iniciar."""

    def __init__(self, **kwargs):
        raise RuntimeError("no se pudo abrir el stream")


class _FakeDefault:
    """Reemplaza ``sounddevice.default`` para no disparar validaciones de PortAudio."""

    def __init__(self, device: tuple[int, int]):
        self.device = device


@pytest.fixture(autouse=True)
def _sesion_limpia(monkeypatch):
    """Aisla cada test reemplazando el estado global de grabacion."""
    monkeypatch.setattr(play_record, "_recording_session", play_record.RecordingSession())
    FakeInputStream.instances.clear()
    yield


@pytest.fixture
def repo_tmp(monkeypatch, tmp_path):
    """Redirige obtener_repo_root() a un directorio temporal con su propio pyproject.toml."""
    (tmp_path / "subdir").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path / "subdir")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return tmp_path


# ── device / divice ──────────────────────────────────────────────────────


class TestDevice:
    def test_device_expone_defaults_y_lista(self, monkeypatch):
        monkeypatch.setattr(play_record.sd, "default", _FakeDefault((2, 3)))
        fake_devices = [
            {"name": "Mic", "max_input_channels": np.int64(2), "max_output_channels": 0},
            {"name": "Speaker", "max_input_channels": 0, "max_output_channels": np.int64(2)},
        ]
        monkeypatch.setattr(play_record.sd, "query_devices", lambda: fake_devices)

        info = play_record.device()

        assert info["default_input_device"] == 2
        assert info["default_output_device"] == 3
        assert info["devices"][0]["name"] == "Mic"
        assert info["devices"][0]["max_input_channels"] == 2
        assert isinstance(info["devices"][0]["max_input_channels"], int)

    def test_divice_es_alias_de_device(self, monkeypatch):
        monkeypatch.setattr(play_record.sd, "default", _FakeDefault((0, 0)))
        monkeypatch.setattr(play_record.sd, "query_devices", lambda: [])
        assert play_record.divice() == play_record.device()


# ── obtener_repo_root / obtener_ruta_audio / guardar_audio_subido ─────────


class TestRutasYArchivos:
    def test_obtener_repo_root_busca_hacia_arriba(self, repo_tmp):
        assert play_record.obtener_repo_root() == repo_tmp

    def test_obtener_repo_root_usa_cwd_si_no_encuentra(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert play_record.obtener_repo_root() == tmp_path

    def test_obtener_ruta_audio_valida(self, repo_tmp):
        ruta = play_record.obtener_ruta_audio("clip.wav")
        assert ruta == repo_tmp / "data" / "clip.wav"

    def test_obtener_ruta_audio_rechaza_subdirectorios(self, repo_tmp):
        with pytest.raises(ValueError, match="invalido"):
            play_record.obtener_ruta_audio("../etc/passwd")

    def test_obtener_ruta_audio_rechaza_vacio(self, repo_tmp):
        with pytest.raises(ValueError, match="invalido"):
            play_record.obtener_ruta_audio("")

    def test_guardar_audio_subido_escribe_bytes(self, repo_tmp):
        ruta = play_record.guardar_audio_subido(b"contenido-binario", "subida.wav")
        assert ruta.parent == repo_tmp / "data"
        assert ruta.read_bytes() == b"contenido-binario"

    def test_guardar_audio_subido_vacio_lanza_error(self, repo_tmp):
        with pytest.raises(ValueError, match="vacio"):
            play_record.guardar_audio_subido(b"", "x.wav")

    def test_obtener_media_type_audio_conocido(self):
        esperado = mimetypes.guess_type("clip.wav")[0]
        assert play_record.obtener_media_type_audio("clip.wav") == esperado

    def test_obtener_media_type_audio_desconocido(self):
        assert play_record.obtener_media_type_audio("clip.extension-rara") == (
            "application/octet-stream"
        )


class TestGuardarAudioValidaciones:
    def test_guardar_audio_ndim_invalido(self):
        with pytest.raises(ValueError, match="1D"):
            play_record.guardar_audio(np.zeros((2, 2, 2), dtype=np.float32), 44100)

    def test_guardar_audio_fs_invalido(self):
        with pytest.raises(ValueError, match="fs"):
            play_record.guardar_audio(np.ones(10, dtype=np.float32), 0)

    def test_guardar_audio_nombre_vacio(self):
        with pytest.raises(ValueError, match="nombre_archivo"):
            play_record.guardar_audio(np.ones(10, dtype=np.float32), 44100, "")


class TestReproducirYGrabarValidaciones:
    def test_ndim_invalido(self):
        with pytest.raises(ValueError, match="1D"):
            play_record.reproducir_y_grabar(np.zeros((2, 2, 2), dtype=np.float32), 8000, 1.0)

    def test_senal_vacia(self):
        with pytest.raises(ValueError, match="vacia"):
            play_record.reproducir_y_grabar(np.array([], dtype=np.float32), 8000, 1.0)

    def test_fs_invalido(self):
        with pytest.raises(ValueError, match="fs"):
            play_record.reproducir_y_grabar(np.ones(10, dtype=np.float32), 0, 1.0)

    def test_duracion_grabacion_invalida(self):
        with pytest.raises(ValueError, match="duracion_grabacion"):
            play_record.reproducir_y_grabar(np.ones(10, dtype=np.float32), 8000, 0.0)


# ── RecordingSession ───────────────────────────────────────────────────────


class TestRecordingSession:
    def test_callback_acumula_frames(self):
        session = play_record.RecordingSession()
        bloque = np.ones((10, 1), dtype=np.float32)
        session.callback(bloque, 10, None, None)
        session.callback(bloque, 10, None, None)
        assert len(session.frames) == 2
        np.testing.assert_array_equal(session.frames[0], bloque)

    def test_reset_active_limpia_estado_activo(self):
        session = play_record.RecordingSession(
            stream=object(), fs=8000, channels=1, frames=[np.zeros(1)]
        )
        session.reset_active()
        assert session.stream is None
        assert session.fs is None
        assert session.channels is None
        assert session.frames == []


# ── iniciar_grabacion / estado_grabacion / detener_grabacion ──────────────


class TestCicloDeGrabacion:
    def test_iniciar_y_detener_grabacion_mono_guarda_audio(self, monkeypatch, repo_tmp):
        monkeypatch.setattr(play_record.sd, "check_input_settings", lambda **kw: None)
        monkeypatch.setattr(play_record.sd, "InputStream", FakeInputStream)

        estado = play_record.iniciar_grabacion(
            fs=8000, canales=1, auto_stop_seconds=120, nombre_archivo="manual.wav"
        )
        assert estado["recording"] is True
        assert estado["fs"] == 8000
        assert estado["canales"] == 1
        assert estado["nombre_archivo"] == "manual.wav"

        stream = FakeInputStream.instances[-1]
        assert stream.started is True

        bloque = np.ones((100, 1), dtype=np.float32)
        play_record._recording_session.callback(bloque, 100, None, None)
        play_record._recording_session.callback(bloque, 100, None, None)

        intermedio = play_record.estado_grabacion()
        assert intermedio["recording"] is True
        assert intermedio["duracion_actual"] >= 0

        audio, fs_out, ruta, estado_final = play_record.detener_grabacion(guardar_archivo=True)

        assert fs_out == 8000
        assert audio.shape == (200,)
        assert ruta == repo_tmp / "data" / "manual.wav"
        assert ruta.exists()
        assert stream.stopped is True
        assert stream.closed is True
        assert estado_final["recording"] is False
        assert estado_final["ultimo_motivo_fin"] == "manual"
        assert estado_final["ultimo_archivo_guardado"] == "manual.wav"

    def test_iniciar_y_detener_grabacion_estereo_no_hace_squeeze(self, monkeypatch, repo_tmp):
        monkeypatch.setattr(play_record.sd, "check_input_settings", lambda **kw: None)
        monkeypatch.setattr(play_record.sd, "InputStream", FakeInputStream)

        play_record.iniciar_grabacion(fs=8000, canales=2, auto_stop_seconds=120)
        bloque = np.ones((50, 2), dtype=np.float32)
        play_record._recording_session.callback(bloque, 50, None, None)

        audio, _fs, _ruta, _estado = play_record.detener_grabacion(guardar_archivo=False)
        assert audio.shape == (50, 2)

    def test_iniciar_grabacion_mientras_hay_otra_activa_lanza_error(self, monkeypatch, repo_tmp):
        monkeypatch.setattr(play_record.sd, "check_input_settings", lambda **kw: None)
        monkeypatch.setattr(play_record.sd, "InputStream", FakeInputStream)

        play_record.iniciar_grabacion(fs=8000, canales=1, auto_stop_seconds=120)
        with pytest.raises(RuntimeError, match="ya hay una grabacion en curso"):
            play_record.iniciar_grabacion(fs=8000, canales=1, auto_stop_seconds=120)

        play_record._recording_session.callback(
            np.ones((10, 1), dtype=np.float32), 10, None, None
        )
        play_record.detener_grabacion(guardar_archivo=False)

    def test_detener_grabacion_sin_grabacion_activa_lanza_error(self):
        with pytest.raises(RuntimeError, match="no hay una grabacion en curso"):
            play_record.detener_grabacion()

    def test_detener_grabacion_sin_frames_lanza_error(self, monkeypatch, repo_tmp):
        monkeypatch.setattr(play_record.sd, "check_input_settings", lambda **kw: None)
        monkeypatch.setattr(play_record.sd, "InputStream", FakeInputStream)

        play_record.iniciar_grabacion(fs=8000, canales=1, auto_stop_seconds=120)
        with pytest.raises(RuntimeError, match="no se capturaron muestras"):
            play_record.detener_grabacion()

        estado = play_record.estado_grabacion()
        assert estado["recording"] is False
        assert estado["ultimo_motivo_fin"] == "sin_muestras"

    def test_detener_grabacion_error_al_parar_stream(self, monkeypatch, repo_tmp):
        monkeypatch.setattr(play_record.sd, "check_input_settings", lambda **kw: None)
        monkeypatch.setattr(play_record.sd, "InputStream", FakeInputStream)

        play_record.iniciar_grabacion(fs=8000, canales=1, auto_stop_seconds=120)
        stream = FakeInputStream.instances[-1]
        stream.raise_on_stop = True

        with pytest.raises(RuntimeError, match="detener la grabacion"):
            play_record.detener_grabacion()

        estado = play_record.estado_grabacion()
        assert estado["recording"] is False
        assert estado["ultimo_motivo_fin"] == "error_stop"

    def test_auto_detener_y_guardar_grabacion_guarda_con_motivo_auto(self, monkeypatch, repo_tmp):
        monkeypatch.setattr(play_record.sd, "check_input_settings", lambda **kw: None)
        monkeypatch.setattr(play_record.sd, "InputStream", FakeInputStream)

        play_record.iniciar_grabacion(fs=8000, canales=1, auto_stop_seconds=120)
        bloque = np.ones((20, 1), dtype=np.float32)
        play_record._recording_session.callback(bloque, 20, None, None)

        play_record._auto_detener_y_guardar_grabacion()

        estado = play_record.estado_grabacion()
        assert estado["recording"] is False
        assert estado["ultimo_motivo_fin"] == "auto_stop"
        assert estado["ultimo_archivo_guardado"] is not None

    def test_auto_detener_y_guardar_grabacion_no_propaga_excepcion(self):
        # No hay grabacion activa: _finalizar_grabacion lanza RuntimeError,
        # pero el callback del timer debe atraparla y no propagarla.
        play_record._auto_detener_y_guardar_grabacion()

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"fs": 0, "canales": 1}, "fs"),
            ({"fs": 8000, "canales": 0}, "canales"),
            ({"fs": 8000, "canales": 1, "nombre_archivo": ""}, "nombre_archivo"),
            ({"fs": 8000, "canales": 1, "auto_stop_seconds": 0}, "auto_stop_seconds"),
        ],
    )
    def test_iniciar_grabacion_valida_parametros(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            play_record.iniciar_grabacion(**kwargs)

    def test_iniciar_grabacion_port_audio_error_resetea_sesion(self, monkeypatch):
        def fake_check(**kwargs):
            raise play_record.sd.PortAudioError("sin dispositivo de entrada")

        monkeypatch.setattr(play_record.sd, "check_input_settings", fake_check)

        with pytest.raises(RuntimeError, match="dispositivo de entrada"):
            play_record.iniciar_grabacion(fs=8000, canales=1)

        assert play_record.estado_grabacion()["recording"] is False

    def test_iniciar_grabacion_error_generico_resetea_sesion(self, monkeypatch):
        monkeypatch.setattr(play_record.sd, "check_input_settings", lambda **kw: None)
        monkeypatch.setattr(play_record.sd, "InputStream", RaisingInputStream)

        with pytest.raises(RuntimeError, match="Error al iniciar la grabacion"):
            play_record.iniciar_grabacion(fs=8000, canales=1)

        assert play_record.estado_grabacion()["recording"] is False


# ── reproducir_audio_guardado ──────────────────────────────────────────────


class TestReproducirAudioGuardado:
    def test_archivo_inexistente_lanza_file_not_found(self, repo_tmp):
        with pytest.raises(FileNotFoundError):
            play_record.reproducir_audio_guardado("no_existe.wav")

    def test_reproduce_audio_mono_guardado(self, monkeypatch, repo_tmp):
        carpeta_datos = repo_tmp / "data"
        carpeta_datos.mkdir(parents=True, exist_ok=True)
        senal = np.linspace(-1, 1, 4000, dtype=np.float32)
        sf.write(str(carpeta_datos / "clip.wav"), senal, 8000)

        llamada: dict[str, object] = {}
        monkeypatch.setattr(
            play_record.sd, "check_output_settings", lambda **kw: llamada.update(kw)
        )
        monkeypatch.setattr(
            play_record.sd, "play", lambda *a, **kw: llamada.__setitem__("play", True)
        )

        resultado = play_record.reproducir_audio_guardado(
            "clip.wav", output_device=None, blocking=True
        )

        assert resultado["nombre_archivo"] == "clip.wav"
        assert resultado["fs"] == 8000
        assert resultado["cantidad_canales"] == 1
        assert resultado["cantidad_muestras"] == 4000
        assert llamada.get("play") is True

    def test_reproducir_audio_guardado_port_audio_error(self, monkeypatch, repo_tmp):
        carpeta_datos = repo_tmp / "data"
        carpeta_datos.mkdir(parents=True, exist_ok=True)
        sf.write(str(carpeta_datos / "clip.wav"), np.zeros(100, dtype=np.float32), 8000)

        def fake_check(**kwargs):
            raise play_record.sd.PortAudioError("sin dispositivo de salida")

        monkeypatch.setattr(play_record.sd, "check_output_settings", fake_check)

        with pytest.raises(RuntimeError, match="dispositivo de salida"):
            play_record.reproducir_audio_guardado("clip.wav")

    def test_reproducir_audio_guardado_error_generico(self, monkeypatch, repo_tmp):
        carpeta_datos = repo_tmp / "data"
        carpeta_datos.mkdir(parents=True, exist_ok=True)
        sf.write(str(carpeta_datos / "clip.wav"), np.zeros(100, dtype=np.float32), 8000)

        monkeypatch.setattr(play_record.sd, "check_output_settings", lambda **kw: None)

        def fake_play(*args, **kwargs):
            raise RuntimeError("fallo inesperado")

        monkeypatch.setattr(play_record.sd, "play", fake_play)

        with pytest.raises(RuntimeError, match="Error al reproducir"):
            play_record.reproducir_audio_guardado("clip.wav")


# ── _to_builtin ─────────────────────────────────────────────────────────────


class TestToBuiltin:
    def test_convierte_escalares_numpy(self):
        assert play_record._to_builtin(np.int64(5)) == 5
        assert isinstance(play_record._to_builtin(np.int64(5)), int)

    def test_convierte_recursivamente_dict_list_tuple(self):
        valor = {"a": [np.float32(1.5), (np.int32(2),)]}
        convertido = play_record._to_builtin(valor)
        assert convertido == {"a": [1.5, (2,)]}
        assert isinstance(convertido["a"][0], float)

    def test_deja_tipos_planos_sin_cambios(self):
        assert play_record._to_builtin("texto") == "texto"
        assert play_record._to_builtin(3) == 3
