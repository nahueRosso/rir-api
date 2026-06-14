"""Tests para los servicios de procesamiento de senales (Milestone 2)."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import freqz

from app.services.filter import filtro_octava
from app.services.signal_utils import (
    a_escala_log,
    cargar_audio,
    obtener_ri_desde_sweep,
    sintetizar_ri,
)
from app.services.sine_sweep import generar_sine_sweep


# ─── helpers ────────────────────────────────────────────────────────────────

def _wav_tmp(senal: np.ndarray, fs: int) -> Path:
    """Escribe senal a un archivo WAV temporal y devuelve su Path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, senal, fs, subtype="PCM_16")
    return Path(tmp.name)


# ─── cargar_audio ────────────────────────────────────────────────────────────

class TestCargarAudio:
    def test_archivo_no_existe(self):
        with pytest.raises(FileNotFoundError):
            cargar_audio("no_existe.wav")

    def test_formato_invalido(self):
        with pytest.raises(ValueError, match="Formato no soportado"):
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(b"dummy")
                cargar_audio(f.name)

    def test_carga_wav(self):
        fs = 44100
        senal_orig = np.sin(2 * np.pi * 440 * np.arange(fs) / fs).astype(np.float32)
        ruta = _wav_tmp(senal_orig, fs)
        senal, fs_out = cargar_audio(ruta)
        assert fs_out == fs
        assert isinstance(senal, np.ndarray)
        assert senal.dtype == np.float64

    def test_normalizacion(self):
        """Salida debe estar entre -1 y 1."""
        fs = 44100
        senal_orig = (np.random.randn(fs) * 0.5).astype(np.float32)
        ruta = _wav_tmp(senal_orig, fs)
        senal, _ = cargar_audio(ruta)
        assert np.max(np.abs(senal)) <= 1.0 + 1e-6


# ─── sintetizar_ri ───────────────────────────────────────────────────────────

class TestSintetizarRi:
    T60_BANDAS = {125: 2.0, 250: 1.8, 500: 1.5, 1000: 1.2, 2000: 1.0, 4000: 0.8}

    def test_duracion_correcta(self):
        fs, dur = 44100, 3.0
        ri = sintetizar_ri(self.T60_BANDAS, fs, dur)
        assert abs(len(ri) / fs - dur) < 0.01

    def test_retorna_ndarray(self):
        ri = sintetizar_ri(self.T60_BANDAS, 44100, 2.0)
        assert isinstance(ri, np.ndarray)

    def test_normalizada(self):
        ri = sintetizar_ri(self.T60_BANDAS, 44100, 2.0)
        assert np.max(np.abs(ri)) <= 1.0 + 1e-6

    def test_decaimiento_aproximado(self):
        """
        Sintetiza con T60=2s en 1000 Hz, filtra la RI en esa banda y verifica
        que el tiempo en cruzar -60 dB esta dentro del 20% del valor esperado.
        """
        fs = 44100
        t60_objetivo = 2.0
        ri = sintetizar_ri({1000: t60_objetivo}, fs, 4.0)

        # Filtrar en la banda de 1000 Hz
        ri_banda = filtro_octava(ri, 1000, fs)

        # Curva de decaimiento en dB
        db = a_escala_log(ri_banda)

        # Encontrar tiempo en cruzar -60 dB
        tiempo = np.arange(len(db)) / fs
        indices_bajo = np.where(db <= -60)[0]
        if len(indices_bajo) == 0:
            pytest.skip("RI demasiado corta para cruzar -60 dB")

        t60_medido = tiempo[indices_bajo[0]]
        tolerancia = 0.20 * t60_objetivo
        assert abs(t60_medido - t60_objetivo) < tolerancia, (
            f"T60 medido={t60_medido:.2f} s, esperado={t60_objetivo} s"
        )


# ─── obtener_ri_desde_sweep ──────────────────────────────────────────────────

class TestObtenerRiDesdeSweep:
    def test_pico_principal_identificable(self):
        """La RI recuperada debe tener un pico claramente mayor al resto."""
        fs = 44100
        sweep, filtro = generar_sine_sweep(20, 20000, 3.0, fs, "logaritmico")

        # Simular grabacion en sala sin reflexiones (convolucion con delta)
        delta = np.zeros(fs)
        delta[0] = 1.0
        grabacion = np.convolve(sweep, delta)[:len(sweep)]

        ri = obtener_ri_desde_sweep(grabacion, filtro)

        pico = np.max(np.abs(ri))
        energia_resto = np.mean(ri[100:] ** 2) if len(ri) > 100 else 0
        snr_db = 10 * np.log10(pico**2 / (energia_resto + 1e-12))
        assert snr_db > 20, f"SNR del pico insuficiente: {snr_db:.1f} dB"

    def test_retorna_normalizada(self):
        fs = 44100
        sweep, filtro = generar_sine_sweep(20, 20000, 2.0, fs, "logaritmico")
        ri = obtener_ri_desde_sweep(sweep, filtro)
        assert np.max(np.abs(ri)) <= 1.0 + 1e-6

    def test_longitud_razonable(self):
        fs = 44100
        sweep, filtro = generar_sine_sweep(20, 20000, 2.0, fs, "logaritmico")
        ri = obtener_ri_desde_sweep(sweep, filtro)
        # La RI debe tener al menos 1 muestra y a lo sumo sweep+filtro-1
        assert len(ri) >= 1
        assert len(ri) <= len(sweep) + len(filtro) - 1


# ─── filtro_octava ───────────────────────────────────────────────────────────

class TestFiltroOctava:
    FS = 44100

    def test_pasa_frecuencia_central(self):
        """Sinusoide en fc debe pasar con ganancia cercana a 0 dB."""
        fc = 1000
        t = np.arange(self.FS * 2) / self.FS
        senal = np.sin(2 * np.pi * fc * t).astype(np.float32)
        filtrada = filtro_octava(senal, fc, self.FS)
        rms_in = np.sqrt(np.mean(senal[self.FS:] ** 2))
        rms_out = np.sqrt(np.mean(filtrada[self.FS:] ** 2))
        ganancia_db = 20 * np.log10(rms_out / rms_in)
        assert ganancia_db > -3.0, f"Ganancia en fc={fc} Hz: {ganancia_db:.1f} dB"

    def test_atenuacion_fuera_de_banda(self):
        """Sinusoide a 3 octavas de fc debe ser fuertemente atenuada."""
        fc = 1000
        f_fuera = fc * 8  # 3 octavas arriba
        if f_fuera >= self.FS / 2:
            pytest.skip("Frecuencia fuera de banda excede Nyquist")
        t = np.arange(self.FS * 2) / self.FS
        senal = np.sin(2 * np.pi * f_fuera * t).astype(np.float32)
        filtrada = filtro_octava(senal, fc, self.FS)
        rms_in = np.sqrt(np.mean(senal[self.FS:] ** 2))
        rms_out = np.sqrt(np.mean(filtrada[self.FS:] ** 2)) + 1e-12
        atenuacion_db = 20 * np.log10(rms_in / rms_out)
        assert atenuacion_db > 20, f"Atenuacion fuera de banda: {atenuacion_db:.1f} dB"

    def test_frecuencia_nyquist_invalida(self):
        """Banda que supera Nyquist debe lanzar ValueError."""
        with pytest.raises(ValueError):
            filtro_octava(np.ones(1000, dtype=np.float32), fc=16000, fs=22050)

    def test_respuesta_frecuencia_corte(self):
        """La ganancia en f_inf y f_sup debe estar cerca de -3 dB."""
        fc = 1000
        orden = 4
        f_inf = fc / np.sqrt(2)
        f_sup = fc * np.sqrt(2)
        nyq = self.FS / 2

        b, a = __import__("scipy").signal.butter(
            orden,
            [f_inf / nyq, f_sup / nyq],
            btype="band",
        )
        w, h = freqz(b, a, worN=8192, fs=self.FS)

        mag_db = 20 * np.log10(np.abs(h) + 1e-12)

        def ganancia_en(f):
            idx = np.argmin(np.abs(w - f))
            return mag_db[idx]

        assert abs(ganancia_en(f_inf) - (-3.0)) < 2.0
        assert abs(ganancia_en(f_sup) - (-3.0)) < 2.0


# ─── a_escala_log ────────────────────────────────────────────────────────────

class TestAEscalaLog:
    def test_maximo_es_cero_db(self):
        x = np.array([1.0, 0.5, 0.25])
        db = a_escala_log(x)
        assert abs(db[0]) < 1e-10

    def test_mitad_amplitud_es_menos_6db(self):
        x = np.array([1.0, 0.5])
        db = a_escala_log(x)
        assert abs(db[1] - (-6.02)) < 0.1

    def test_tipo_retorno(self):
        db = a_escala_log(np.array([1.0, 0.5]))
        assert isinstance(db, np.ndarray)
        assert db.dtype == np.float64

    def test_senal_vacia_lanza_error(self):
        with pytest.raises(ValueError):
            a_escala_log(np.array([]))

    def test_piso_minimo(self):
        """Valores muy pequenos no deben dar -inf."""
        x = np.array([1.0, 1e-10])
        db = a_escala_log(x)
        assert np.all(np.isfinite(db))
        assert db[1] >= -120.0
