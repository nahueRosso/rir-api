"""Tests para los servicios de generacion de senales (Milestone 1)."""

import numpy as np

from app.services.pink_noise import generar_ruido_rosa
from app.services.play_record import reproducir_y_grabar
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
