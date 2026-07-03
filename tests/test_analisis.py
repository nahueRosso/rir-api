"""Tests para los servicios de analisis de parametros acusticos (Milestone 3)."""

import numpy as np

from app.services.acoustic_parameters import (
    calcular_parametros_acusticos,
    integral_schroeder,
    metodo_lundeby,
    regresion_lineal,
    suavizar_signal,
)
from app.services.signal_utils import sintetizar_ri


class TestSuavizarSignal:
    """Tests para la funcion suavizar_signal."""

    def test_hilbert_envolvente_no_negativa(self):
        """La envolvente de Hilbert debe ser no negativa."""
        senal = np.sin(2 * np.pi * 100 * np.arange(1000) / 8000)
        envolvente = suavizar_signal(senal, "hilbert")
        assert np.all(envolvente >= 0)
        assert len(envolvente) == len(senal)

    def test_media_movil_longitud(self):
        """La salida por media movil debe tener la misma longitud que la entrada."""
        senal = np.random.randn(1000)
        suavizada = suavizar_signal(senal, 50)
        assert len(suavizada) == len(senal)

    def test_ventana_invalida_lanza_error(self):
        """Una ventana de texto distinta de 'hilbert' debe lanzar ValueError."""
        try:
            suavizar_signal(np.random.randn(10), "media")
        except ValueError:
            pass
        else:
            raise AssertionError("Se esperaba ValueError")


class TestRegresionLineal:
    """Tests para la funcion regresion_lineal."""

    def test_regresion_lineal_exacta(self):
        """Para datos perfectamente lineales, R^2 debe ser 1.0."""
        x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        y = 2.0 * x + 1.0
        pendiente, ordenada, r_cuadrado = regresion_lineal(x, y)
        assert abs(pendiente - 2.0) < 1e-10
        assert abs(ordenada - 1.0) < 1e-10
        assert abs(r_cuadrado - 1.0) < 1e-10

    def test_regresion_lineal_con_ruido(self):
        """Verifica que la regresion se aproxima a la recta con datos ruidosos."""
        np.random.seed(42)
        x = np.linspace(0, 10, 100)
        y = 3.0 * x + 5.0 + np.random.normal(0, 0.1, 100)
        pendiente, ordenada, r_cuadrado = regresion_lineal(x, y)
        assert abs(pendiente - 3.0) < 0.5
        assert abs(ordenada - 5.0) < 1.0
        assert r_cuadrado > 0.9


class TestIntegralSchroeder:
    """Tests para la funcion integral_schroeder."""

    def test_integral_schroeder_forma(self):
        """Verifica que la EDC tiene la misma longitud que la entrada."""
        ri = np.random.randn(1000)
        edc = integral_schroeder(ri)
        assert len(edc) == len(ri)

    def test_integral_schroeder_maximo_cero_db(self):
        """El primer valor de la EDC debe ser aproximadamente 0 dB."""
        ri = np.random.randn(1000)
        edc = integral_schroeder(ri)
        assert abs(edc[0]) < 1e-6

    def test_integral_schroeder_decreciente(self):
        """Verifica que la EDC es monotonamente decreciente."""
        ri = np.random.randn(1000)
        edc = integral_schroeder(ri)
        assert np.all(np.diff(edc) <= 0)

    def test_integral_schroeder_ri_sintetizada(self):
        """Para una RI exponencial con T60 conocido, la pendiente de la EDC
        debe aproximarse a -60/T60 dB/s."""
        fs = 16000
        t60 = 1.0
        duracion = 2.0
        n = int(duracion * fs)
        t = np.arange(n) / fs
        alpha = 3.0 * np.log(10.0) / t60
        rng = np.random.default_rng(0)
        ri = rng.standard_normal(n) * np.exp(-alpha * t)

        edc = integral_schroeder(ri)
        pendiente, _, _ = regresion_lineal(t[: n // 2], edc[: n // 2])
        t60_estimado = -60.0 / pendiente
        assert abs(t60_estimado - t60) / t60 < 0.15


class TestCalcularParametrosAcusticos:
    """Tests para la funcion calcular_parametros_acusticos con una RI sintetizada."""

    def _generar_ri(self, fc: float, t60: float, fs: int = 16000, duracion: float = 3.0):
        return sintetizar_ri({fc: t60}, fs, duracion)

    def test_t30_dentro_de_tolerancia(self):
        """T30 debe estar dentro del +-15% del T60 usado para sintetizar la RI."""
        fs = 16000
        t60 = 1.5
        ri = self._generar_ri(1000.0, t60, fs=fs)
        parametros = calcular_parametros_acusticos(ri, fs)
        t30 = parametros["T30"]["1000"]
        assert not np.isnan(t30)
        assert abs(t30 - t60) / t60 < 0.15

    def test_d50_en_rango(self):
        """D50 debe estar entre 0% y 100%."""
        ri = self._generar_ri(1000.0, 1.0)
        parametros = calcular_parametros_acusticos(ri, 16000)
        d50 = parametros["D50"]["1000"]
        assert 0.0 <= d50 <= 100.0

    def test_c80_es_finito(self):
        """C80 debe ser un valor finito para una RI valida."""
        ri = self._generar_ri(1000.0, 1.0)
        parametros = calcular_parametros_acusticos(ri, 16000)
        c80 = parametros["C80"]["1000"]
        assert np.isfinite(c80)

    def test_estructura_por_banda(self):
        """El diccionario resultante debe tener las claves de parametros esperadas."""
        ri = self._generar_ri(1000.0, 1.0)
        parametros = calcular_parametros_acusticos(ri, 16000)
        for clave in ("EDT", "T10", "T20", "T30", "T60", "D50", "C80"):
            assert clave in parametros
            assert "1000" in parametros[clave]


class TestMetodoLundeby:
    """Tests basicos para el metodo de Lundeby (extra credit)."""

    def test_devuelve_indice_y_nivel_de_ruido(self):
        fs = 16000
        t60 = 1.0
        duracion = 2.0
        n = int(duracion * fs)
        t = np.arange(n) / fs
        alpha = 3.0 * np.log(10.0) / t60
        rng = np.random.default_rng(1)
        ruido = rng.standard_normal(n) * 0.001
        ri = rng.standard_normal(n) * np.exp(-alpha * t) + ruido

        indice, nivel_ruido = metodo_lundeby(ri, fs)
        assert 0 < indice < n
        assert np.isfinite(nivel_ruido)
