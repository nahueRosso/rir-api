"""Tests para el modulo de streaming SSE (services/streaming.py y routers/streaming.py)."""

from __future__ import annotations

import base64
import io
import json

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from matplotlib.figure import Figure

from app.main import app
from app.routers.streaming import _leer_audio_bytes, _sanear_nan
from app.services.streaming import StreamingProcessor

client = TestClient(app)


def _wav_bytes(t60: float = 1.0, fs: int = 44100, duracion: float = 1.0) -> bytes:
    """Genera un WAV en memoria con una RI exponencial sintetica."""
    n = int(duracion * fs)
    t = np.arange(n) / fs
    alpha = 3.0 * np.log(10.0) / t60
    rng = np.random.default_rng(0)
    ri = (rng.standard_normal(n) * np.exp(-alpha * t)).astype(np.float32)
    ri /= np.max(np.abs(ri))

    buf = io.BytesIO()
    sf.write(buf, ri, fs, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()


def _parse_sse(text: str) -> list[dict]:
    """Parsea un cuerpo de respuesta SSE (varios `data: {...}\\n\\n`) a una lista de dicts."""
    eventos = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        assert chunk.startswith("data: ")
        eventos.append(json.loads(chunk[len("data: "):]))
    return eventos


# ── services/streaming.py: StreamingProcessor ──────────────────────────────


class TestFormatSse:
    def test_format_sse_produce_data_prefix_y_doble_salto(self):
        salida = StreamingProcessor.format_sse({"a": 1})
        assert salida.startswith("data: ")
        assert salida.endswith("\n\n")

    def test_format_sse_es_json_valido(self):
        payload = {"step": "x", "message": "y", "n": 3}
        salida = StreamingProcessor.format_sse(payload)
        cuerpo = salida[len("data: "):-2]
        assert json.loads(cuerpo) == payload

    def test_format_sse_soporta_no_ascii(self):
        salida = StreamingProcessor.format_sse({"message": "señal ñ"})
        assert "señal ñ" in salida


class TestStepEvent:
    def test_step_event_campos_minimos(self):
        evento = _parse_sse(StreamingProcessor.step_event("cargando", "Leyendo..."))[0]
        assert evento["step"] == "cargando"
        assert evento["message"] == "Leyendo..."
        assert "timestamp" in evento
        assert "tiempo_ms" not in evento
        assert "grafico" not in evento
        assert "audio" not in evento

    def test_step_event_incluye_tiempo_ms_redondeado(self):
        evento = _parse_sse(
            StreamingProcessor.step_event("paso", "msg", tiempo_ms=12.3456)
        )[0]
        assert evento["tiempo_ms"] == 12.3

    def test_step_event_incluye_grafico_audio_y_audios(self):
        evento = _parse_sse(
            StreamingProcessor.step_event(
                "completado",
                "listo",
                grafico="base64grafico",
                audio="base64audio",
                audio_filename="out.wav",
                audios=[{"filename": "a.wav", "data": "xx"}],
            )
        )[0]
        assert evento["grafico"] == "base64grafico"
        assert evento["audio"] == "base64audio"
        assert evento["audio_filename"] == "out.wav"
        assert evento["audios"] == [{"filename": "a.wav", "data": "xx"}]

    def test_step_event_extra_kwargs_se_mezclan_en_payload(self):
        evento = _parse_sse(
            StreamingProcessor.step_event("parametros", "ok", parametros={"T30": {"125": 1.2}})
        )[0]
        assert evento["parametros"] == {"T30": {"125": 1.2}}


class TestGraficoABase64:
    def test_grafico_a_base64_devuelve_png_valido(self):
        fig, ax = StreamingProcessor.crear_figura()
        ax.plot([0, 1, 2], [0, 1, 0])
        b64 = StreamingProcessor.grafico_a_base64(fig)
        raw = base64.b64decode(b64)
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"

    def test_crear_figura_respeta_figsize(self):
        fig, ax = StreamingProcessor.crear_figura(figsize=(4, 1.5))
        assert isinstance(fig, Figure)
        assert tuple(fig.get_size_inches()) == (4, 1.5)


class TestAudioABase64:
    def test_audio_a_base64_es_wav_reproducible(self):
        fs = 8000
        senal = np.sin(2 * np.pi * 440 * np.arange(fs) / fs).astype(np.float32)
        b64 = StreamingProcessor.audio_a_base64(senal, fs)
        raw = base64.b64decode(b64)
        leida, fs_leido = sf.read(io.BytesIO(raw), dtype="float32")
        assert fs_leido == fs
        assert len(leida) == len(senal)
        np.testing.assert_allclose(leida, senal, atol=1e-4)


# ── routers/streaming.py: helpers internos ─────────────────────────────────


class TestLeerAudioBytes:
    def test_leer_audio_bytes_valido(self):
        senal, fs = _leer_audio_bytes(_wav_bytes(fs=16000))
        assert fs == 16000
        assert isinstance(senal, np.ndarray)

    def test_leer_audio_bytes_invalido_lanza_value_error(self):
        try:
            _leer_audio_bytes(b"esto no es un wav")
        except ValueError:
            pass
        else:
            raise AssertionError("se esperaba ValueError")


class TestSanearNan:
    def test_sanear_nan_reemplaza_nan_por_none(self):
        entrada = {"T30": {"125": float("nan"), "1000": 1.23}}
        salida = _sanear_nan(entrada)
        assert salida["T30"]["125"] is None
        assert salida["T30"]["1000"] == 1.23


# ── routers/streaming.py: endpoints SSE ────────────────────────────────────


class TestGenerarRuidoRosaStream:
    def test_stream_completa_con_audio(self):
        response = client.post(
            "/api/v1/streaming/generar-ruido-rosa",
            data={"duracion": "0.5", "fs": "8000"},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        pasos = [e["step"] for e in eventos]
        assert "generando" in pasos
        assert "graficando_waveform" in pasos
        assert "graficando_espectro" in pasos
        assert pasos[-1] == "completado"
        assert "audio" in eventos[-1]


class TestGenerarSweepStream:
    def test_stream_logaritmico_completa_con_dos_audios(self):
        response = client.post(
            "/api/v1/streaming/generar-sweep",
            data={"f1": "20", "f2": "2000", "duracion": "0.3", "fs": "8000"},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "completado"
        assert len(eventos[-1]["audios"]) == 2

    def test_stream_lineal_completa(self):
        response = client.post(
            "/api/v1/streaming/generar-sweep",
            data={"f1": "20", "f2": "2000", "duracion": "0.3", "fs": "8000", "tipo": "lineal"},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "completado"

    def test_stream_frecuencias_invalidas_emite_error(self):
        response = client.post(
            "/api/v1/streaming/generar-sweep",
            data={"f1": "2000", "f2": "20", "duracion": "0.3", "fs": "8000"},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "error"


class TestFiltrarBandasStream:
    def test_stream_filtra_todas_las_bandas_por_defecto(self):
        wav = _wav_bytes(fs=44100, duracion=0.5)
        response = client.post(
            "/api/v1/streaming/filtrar-bandas",
            files={"file": ("ri.wav", wav, "audio/wav")},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "completado"
        assert len(eventos[-1]["audios"]) == 6

    def test_stream_bandas_invalidas_emite_error(self):
        wav = _wav_bytes(fs=44100, duracion=0.5)
        response = client.post(
            "/api/v1/streaming/filtrar-bandas",
            files={"file": ("ri.wav", wav, "audio/wav")},
            data={"bandas": "125,abc,500"},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "error"

    def test_stream_banda_no_realizable_se_omite(self):
        wav = _wav_bytes(fs=44100, duracion=0.5)
        response = client.post(
            "/api/v1/streaming/filtrar-bandas",
            files={"file": ("ri.wav", wav, "audio/wav")},
            data={"bandas": "20000"},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "completado"
        assert eventos[-1]["audios"] == []


class TestDesconvolucionarStream:
    def test_stream_completa_con_audio(self):
        from app.services.sine_sweep import generar_sine_sweep

        fs = 8000
        sweep, filtro_inverso = generar_sine_sweep(200, 3000, 0.5, fs)

        grabacion_buf = io.BytesIO()
        sf.write(grabacion_buf, sweep, fs, format="WAV", subtype="FLOAT")
        grabacion_buf.seek(0)

        filtro_buf = io.BytesIO()
        sf.write(filtro_buf, filtro_inverso, fs, format="WAV", subtype="FLOAT")
        filtro_buf.seek(0)

        response = client.post(
            "/api/v1/streaming/desconvolucionar",
            files={
                "grabacion": ("grabacion.wav", grabacion_buf.read(), "audio/wav"),
                "filtro_inverso": ("filtro.wav", filtro_buf.read(), "audio/wav"),
            },
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "completado"
        assert "audio" in eventos[-1]

    def test_stream_fs_distintas_emite_error(self):
        grabacion = _wav_bytes(fs=44100, duracion=0.2)
        filtro = _wav_bytes(fs=16000, duracion=0.2)

        response = client.post(
            "/api/v1/streaming/desconvolucionar",
            files={
                "grabacion": ("grabacion.wav", grabacion, "audio/wav"),
                "filtro_inverso": ("filtro.wav", filtro, "audio/wav"),
            },
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "error"


class TestCalcularParametrosStream:
    def test_stream_completa_con_parametros(self):
        wav = _wav_bytes(fs=44100, duracion=1.0, t60=1.2)
        response = client.post(
            "/api/v1/streaming/calcular-parametros",
            files={"file": ("ri.wav", wav, "audio/wav")},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "completado"
        assert "T30" in eventos[-1]["parametros"]
        assert "1000" in eventos[-1]["parametros"]["T30"]

    def test_stream_audio_invalido_emite_error(self):
        response = client.post(
            "/api/v1/streaming/calcular-parametros",
            files={"file": ("ri.txt", b"no es un wav", "text/plain")},
        )
        assert response.status_code == 200
        eventos = _parse_sse(response.text)
        assert eventos[-1]["step"] == "error"
