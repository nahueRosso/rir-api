"""Tests para los servicios de generacion de senales (Milestone 1)."""

from pathlib import Path

import numpy as np
import pytest
import scipy.signal

from app.services.pink_noise import generar_ruido_rosa
from app.services.play_record import guardar_audio, reproducir_y_grabar
from app.services.sine_sweep import generar_sine_sweep


class TestGenerarRuidoRosa:
    """Tests para la funcion generar_ruido_rosa."""

    def test_ruido_rosa_duracion(self):
        """Verifica que la longitud de la senal corresponda a duracion * fs."""
        duracion = 2.0
        fs = 44100
        ruido = generar_ruido_rosa(duracion, fs)
        expected_length = int(duracion * fs)
        assert len(ruido) == expected_length

    def test_ruido_rosa_tipo(self):
        """Verifica que la funcion retorna un np.ndarray."""
        ruido = generar_ruido_rosa(1.0, 44100)
        assert isinstance(ruido, np.ndarray)

    def test_ruido_rosa_normalizado(self):
        """Verifica que la senal esta normalizada entre -1 y 1."""
        ruido = generar_ruido_rosa(1.0, 44100)
        assert np.max(np.abs(ruido)) <= 1.0

    def test_ruido_rosa_espectro(self):
        """Verifica que el espectro del ruido rosa tiene pendiente de -3 dB/octava."""
        fs = 44100
        ruido = generar_ruido_rosa(duracion=10.0, fs=fs)

        freqs, psd = scipy.signal.welch(ruido, fs=fs, nperseg=fs)

        mask = (freqs >= 100) & (freqs <= 10000)
        freqs_log = np.log2(freqs[mask])
        psd_db = 10 * np.log10(psd[mask])

        pendiente, _ = np.polyfit(freqs_log, psd_db, deg=1)

        assert -4.0 <= pendiente <= -2.0


class TestGenerarSineSweep:
    """Tests para la funcion generar_sine_sweep."""

    def test_sine_sweep_retorna_tupla(self):
        """Verifica que retorna una tupla con dos arrays."""
        resultado = generar_sine_sweep(20, 20000, 1.0, 44100)
        assert isinstance(resultado, tuple)
        assert len(resultado) == 2
        assert isinstance(resultado[0], np.ndarray)
        assert isinstance(resultado[1], np.ndarray)

    def test_sine_sweep_duracion(self):
        """Verifica que ambas senales tienen la longitud correcta."""
        duracion = 3.0
        fs = 44100
        sweep, filtro_inv = generar_sine_sweep(20, 20000, duracion, fs)
        expected_length = int(duracion * fs)
        assert len(sweep) == expected_length
        assert len(filtro_inv) == expected_length

    def test_sine_sweep_lineal_retorna_arrays_normalizados(self):
        """Verifica que el modo lineal genere senales normalizadas."""
        sweep, filtro_inv = generar_sine_sweep(100, 1000, 1.0, 8000, "lineal")
        assert isinstance(sweep, np.ndarray)
        assert isinstance(filtro_inv, np.ndarray)
        assert np.max(np.abs(sweep)) <= 1.0
        assert np.max(np.abs(filtro_inv)) <= 1.0

    def test_sine_sweep_rango_frecuencias(self):
        """Verifica que el sweep cubre el rango de frecuencias especificado."""
        f1, f2 = 20.0, 20000.0
        fs = 44100
        duracion = 5.0
        sweep, _ = generar_sine_sweep(f1, f2, duracion, fs)

        freqs, tiempos, Sxx = scipy.signal.spectrogram(sweep, fs=fs)

        energia_por_tiempo = Sxx.sum(axis=0)
        umbral = energia_por_tiempo.max() * 0.01

        idx_f1 = np.argmin(np.abs(freqs - f1))
        idx_f2 = np.argmin(np.abs(freqs - f2))

        energia_en_f1 = Sxx[idx_f1, : len(tiempos) // 4].max()
        energia_en_f2 = Sxx[idx_f2, len(tiempos) * 3 // 4 :].max()

        assert energia_en_f1 > umbral
        assert energia_en_f2 > umbral

        freq_instantanea = np.array([freqs[Sxx[:, t].argmax()] for t in range(Sxx.shape[1])])
        assert np.all(np.diff(freq_instantanea) >= 0)

    def test_sweep_convolucion_impulso(self):
        """Verifica que la convolucion del sweep con su filtro inverso produce un impulso."""
        fs = 44100
        sweep, filtro_inverso = generar_sine_sweep(20.0, 20000.0, 5.0, fs)

        resultado = scipy.signal.fftconvolve(sweep, filtro_inverso)

        idx_pico = np.argmax(np.abs(resultado))
        amplitud_pico = resultado[idx_pico] ** 2

        ventana = int(0.01 * fs)
        mascara = np.ones(len(resultado), dtype=bool)
        mascara[max(0, idx_pico - ventana) : idx_pico + ventana] = False
        energia_resto = np.mean(resultado[mascara] ** 2)

        ratio_db = 10 * np.log10(amplitud_pico / energia_resto)

        assert ratio_db >= 40.0


class TestReproducirYGrabar:
    """Tests para la funcion reproducir_y_grabar."""

    def test_reproducir_y_grabar_mono_retorna_1d(self, monkeypatch):
        """Verifica que una senal mono produzca una grabacion 1D."""
        fs = 8000
        signal = np.linspace(-1.0, 1.0, fs, dtype=np.float32)

        def fake_check_settings(**kwargs):
            assert kwargs["samplerate"] == fs
            assert kwargs["channels"] == 1
            assert kwargs["dtype"] == "float32"

        def fake_playrec(data, samplerate, channels, dtype):
            assert samplerate == fs
            assert channels == 1
            assert dtype == "float32"
            assert data.ndim == 2
            assert data.shape == (int(1.5 * fs), 1)
            return np.zeros((data.shape[0], channels), dtype=np.float32)

        monkeypatch.setattr(
            "app.services.play_record.sd.check_input_settings",
            fake_check_settings,
        )
        monkeypatch.setattr(
            "app.services.play_record.sd.check_output_settings",
            fake_check_settings,
        )
        monkeypatch.setattr("app.services.play_record.sd.playrec", fake_playrec)
        monkeypatch.setattr("app.services.play_record.sd.wait", lambda: None)

        grabacion = reproducir_y_grabar(signal, fs, duracion_grabacion=1.5)

        assert isinstance(grabacion, np.ndarray)
        assert grabacion.ndim == 1
        assert len(grabacion) == int(1.5 * fs)

    def test_reproducir_y_grabar_estereo_retorna_2d(self, monkeypatch):
        """Verifica que una senal estereo produzca una grabacion 2D."""
        fs = 4000
        signal = np.ones((fs, 2), dtype=np.float32)

        monkeypatch.setattr(
            "app.services.play_record.sd.check_input_settings",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.play_record.sd.check_output_settings",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.play_record.sd.playrec",
            lambda data, samplerate, channels, dtype: np.zeros(
                (data.shape[0], channels), dtype=np.float32
            ),
        )
        monkeypatch.setattr("app.services.play_record.sd.wait", lambda: None)

        grabacion = reproducir_y_grabar(signal, fs, duracion_grabacion=1.25)

        assert grabacion.ndim == 2
        assert grabacion.shape == (int(1.25 * fs), 2)

    def test_reproducir_y_grabar_duracion_insuficiente(self):
        """Verifica que falle si la grabacion dura menos que la senal."""
        signal = np.ones(1000, dtype=np.float32)

        with pytest.raises(ValueError, match="duracion_grabacion"):
            reproducir_y_grabar(signal, fs=1000, duracion_grabacion=0.5)

    def test_reproducir_y_grabar_sin_dispositivo(self, monkeypatch):
        """Verifica que lance una excepcion informativa sin audio disponible."""
        error = RuntimeError("No default input device")

        def fake_check_input_settings(**kwargs):
            _ = kwargs
            raise error

        monkeypatch.setattr(
            "app.services.play_record.sd.check_input_settings",
            fake_check_input_settings,
        )
        monkeypatch.setattr(
            "app.services.play_record.sd.check_output_settings",
            lambda **kwargs: None,
        )
        monkeypatch.setattr("app.services.play_record.sd.playrec", lambda *args, **kwargs: None)
        monkeypatch.setattr("app.services.play_record.sd.wait", lambda: None)

        with pytest.raises(RuntimeError, match="dispositivos de audio"):
            reproducir_y_grabar(
                np.ones(1000, dtype=np.float32),
                fs=1000,
                duracion_grabacion=1.0,
            )


class TestGuardarAudio:
    """Tests para la funcion guardar_audio."""

    def test_guardar_audio_crea_archivo_en_data(self, monkeypatch, tmp_path):
        """Verifica que la funcion escriba en data/ desde la raiz del repo."""
        senal = np.array([0.1, -0.1, 0.2], dtype=np.float32)
        fs = 44100
        llamadas = {}

        (tmp_path / "subdir").mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(tmp_path / "subdir")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")

        def fake_write(path, data, samplerate):
            llamadas["path"] = path
            llamadas["data"] = data
            llamadas["samplerate"] = samplerate

        monkeypatch.setattr("app.services.play_record.sf.write", fake_write)

        ruta = guardar_audio(senal, fs, "mi_audio.wav")

        assert ruta == tmp_path / "data" / "mi_audio.wav"
        assert Path(llamadas["path"]) == ruta
        np.testing.assert_array_equal(llamadas["data"], senal)
        assert llamadas["samplerate"] == fs

    def test_guardar_audio_falla_con_senal_vacia(self):
        """Verifica que falle con una senal vacia."""
        with pytest.raises(ValueError, match="signal no puede estar vacia"):
            guardar_audio(np.array([], dtype=np.float32), 44100)
