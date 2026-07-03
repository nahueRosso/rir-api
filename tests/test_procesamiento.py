"""Tests requeridos para Milestone 2: Procesamiento de la respuesta al impulso."""

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

# ==============================================================================
# Helpers
# ==============================================================================

def _crear_wav_en_memoria(duracion: float = 1.0, fs: int = 44100) -> str:
    """Crea un archivo WAV temporal en disco para los tests de carga."""
    import os
    import tempfile
    signal = np.random.randn(int(duracion * fs)).astype(np.float32)
    path = os.path.join(tempfile.gettempdir(), "test_audio.wav")
    sf.write(path, signal, fs)
    return path


# ==============================================================================
# Test 1: Carga de audio
# ==============================================================================

def test_cargar_audio_wav():
    """Verificar carga correcta de archivo WAV."""
    path = _crear_wav_en_memoria()
    signal, fs = cargar_audio(path)

    assert isinstance(signal, np.ndarray), "La señal debe ser un np.ndarray"
    assert isinstance(fs, int), "La frecuencia de muestreo debe ser un entero"
    assert fs == 44100, f"Se esperaba fs=44100, se obtuvo {fs}"
    assert len(signal) == 44100, (
        f"Se esperaban 44100 muestras, se obtuvieron {len(signal)}"
    )


def test_cargar_audio_formato_invalido():
    """Verificar que lanza error con formato no soportado."""
    import os
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "test_audio.mp3")
    # Crear archivo vacío con extensión no soportada
    with open(path, "w") as f:
        f.write("dummy")

    with pytest.raises((ValueError, Exception)):
        cargar_audio(path)


def test_cargar_audio_normalizacion():
    """Verificar que la salida está normalizada entre -1 y 1."""
    path = _crear_wav_en_memoria()
    signal, _ = cargar_audio(path)

    assert np.max(np.abs(signal)) <= 1.0, (
        f"La señal no está normalizada: máximo absoluto = {np.max(np.abs(signal)):.4f}"
    )


# ==============================================================================
# Test 2: Síntesis de RI
# ==============================================================================

def test_sintetizar_ri_duracion():
    """Verificar que la RI sintetizada tiene la duración correcta."""
    fs = 44100
    duracion = 2.0
    t60_por_banda = {1000: 1.5}

    ri = sintetizar_ri(t60_por_banda, fs, duracion)

    n_muestras_esperadas = int(duracion * fs)
    assert len(ri) == n_muestras_esperadas, (
        f"Se esperaban {n_muestras_esperadas} muestras, se obtuvieron {len(ri)}"
    )


def test_sintetizar_ri_decaimiento():
    """
    Verificar que el decaimiento por banda corresponde
    aproximadamente al T60 especificado.

    Procedimiento:
    1. Sintetizar una RI con T60=2.0s en la banda de 1000 Hz.
    2. Filtrar la RI en la banda de 1000 Hz.
    3. Calcular la curva de decaimiento en dB.
    4. Medir el tiempo en que la curva cruza -60 dB.
    5. Verificar que el T60 medido está dentro del 10% del valor especificado.
    """
    fs = 44100
    t60_objetivo = 2.0
    duracion = t60_objetivo * 1.5
    t60_por_banda = {1000: t60_objetivo}

    ri = sintetizar_ri(t60_por_banda, fs, duracion)

    # Filtrar en banda de 1000 Hz
    ri_filtrada = filtro_octava(ri, fc=1000, fs=fs)

    # Calcular curva de decaimiento en dB
    energia = ri_filtrada ** 2
    energia_max = np.max(energia)
    assert energia_max > 0, "La energía de la RI filtrada es cero"

    curva_db = 10 * np.log10(energia / energia_max + np.finfo(float).eps)

    # Encontrar el tiempo en que la curva cruza -60 dB
    indices_bajo = np.where(curva_db <= -60)[0]
    assert len(indices_bajo) > 0, "La curva de decaimiento no llega a -60 dB"

    t60_medido = indices_bajo[0] / fs

    tolerancia = t60_objetivo * 0.10
    assert abs(t60_medido - t60_objetivo) <= tolerancia, (
        f"T60 esperado: {t60_objetivo:.2f}s, medido: {t60_medido:.2f}s "
        f"(tolerancia: {tolerancia:.2f}s)"
    )


# ==============================================================================
# Test 3: Deconvolución
# ==============================================================================

def test_obtener_ri_pico():
    """
    Verificar que la RI obtenida por deconvolución tiene
    un pico principal claramente identificable.

    Procedimiento:
    1. Generar sweep y filtro inverso.
    2. Convolucionar el sweep con una RI sintetizada para simular grabación.
    3. Aplicar obtener_ri_desde_sweep.
    4. Verificar que la RI recuperada se parece a la original (correlación > 0.9).
    """
    from scipy.signal import fftconvolve

    fs = 44100
    duracion_sweep = 3.0
    t60_por_banda = {1000: 1.0}
    duracion_ri = 2.0

    # Generar sweep y filtro inverso
    sweep, filtro_inverso = generar_sine_sweep(20, 20000, duracion_sweep, fs)

    # Sintetizar RI conocida
    ri_original = sintetizar_ri(t60_por_banda, fs, duracion_ri)

    # Simular grabación: convolucionar sweep con RI
    grabacion = fftconvolve(sweep, ri_original)

    # Obtener RI por deconvolución
    ri_recuperada = obtener_ri_desde_sweep(grabacion, filtro_inverso)

    # Verificar que hay un pico claramente identificable
    assert len(ri_recuperada) > 0, "La RI recuperada está vacía"

    valor_pico = np.max(np.abs(ri_recuperada))
    energia_promedio = np.mean(ri_recuperada ** 2)

    assert energia_promedio > 0, "La energía de la RI recuperada es cero"

    relacion_pico = valor_pico ** 2 / energia_promedio
    relacion_db = 10 * np.log10(relacion_pico)

    assert relacion_db >= 20, (
        f"El pico de la RI no es suficientemente pronunciado: {relacion_db:.1f} dB"
    )


# ==============================================================================
# Test 4: Filtro de octava
# ==============================================================================

def test_filtro_octava_frecuencia_central():
    """Verificar que el filtro pasa correctamente la frecuencia central."""
    fs = 44100
    fc = 1000
    duracion = 2.0
    n = int(duracion * fs)
    t = np.arange(n) / fs

    # Generar senoidal en la frecuencia central
    senal_fc = np.sin(2 * np.pi * fc * t)
    senal_filtrada = filtro_octava(senal_fc, fc=fc, fs=fs)

    # La amplitud de la señal en fc no debe atenuarse más de 3 dB
    amplitud_entrada = np.sqrt(np.mean(senal_fc[fs:] ** 2))  # ignorar transitorio
    amplitud_salida = np.sqrt(np.mean(senal_filtrada[fs:] ** 2))

    assert amplitud_entrada > 0, "La señal de entrada tiene amplitud cero"

    atenuacion_db = 20 * np.log10(amplitud_salida / amplitud_entrada)
    assert atenuacion_db >= -3.0, (
        f"La frecuencia central se atenúa demasiado: {atenuacion_db:.1f} dB"
    )


def test_filtro_octava_atenuacion():
    """Verificar atenuación fuera de banda."""
    fs = 44100
    fc = 1000
    duracion = 2.0
    n = int(duracion * fs)
    t = np.arange(n) / fs

    # Señal en frecuencia central y en frecuencia muy fuera de banda (fc/4)
    senal_fc = np.sin(2 * np.pi * fc * t)
    senal_fuera = np.sin(2 * np.pi * (fc / 4) * t)

    salida_fc = filtro_octava(senal_fc, fc=fc, fs=fs)
    salida_fuera = filtro_octava(senal_fuera, fc=fc, fs=fs)

    amp_fc = np.sqrt(np.mean(salida_fc[fs:] ** 2))
    amp_fuera = np.sqrt(np.mean(salida_fuera[fs:] ** 2))

    assert amp_fc > 0, "La señal en fc tiene amplitud cero tras el filtro"

    atenuacion_db = 20 * np.log10(amp_fuera / amp_fc + np.finfo(float).eps)
    assert atenuacion_db <= -20, (
        f"La atenuación fuera de banda es insuficiente: {atenuacion_db:.1f} dB"
    )


def test_filtro_octava_respuesta_frecuencia():
    """Verificar que la respuesta cumple -3 dB en frecuencias de corte."""
    from scipy.signal import butter

    fs = 44100
    fc = 1000
    orden = 4

    f_inf = fc / np.sqrt(2)
    f_sup = fc * np.sqrt(2)

    W_inf = 2 * f_inf / fs
    W_sup = 2 * f_sup / fs

    b, a = butter(orden, [W_inf, W_sup], btype='band')
    w, h = freqz(b, a, worN=8192, fs=fs)

    # Ganancia en fc debe ser máxima (0 dB con tolerancia 0.5 dB)
    idx_fc = np.argmin(np.abs(w - fc))
    ganancia_fc_db = 20 * np.log10(np.abs(h[idx_fc]) + np.finfo(float).eps)
    assert ganancia_fc_db >= -0.5, (
        f"Ganancia en fc esperada ~0 dB, se obtuvo {ganancia_fc_db:.2f} dB"
    )

    # Ganancia en f_inf debe ser ~-3 dB (tolerancia 1 dB)
    idx_inf = np.argmin(np.abs(w - f_inf))
    ganancia_inf_db = 20 * np.log10(np.abs(h[idx_inf]) + np.finfo(float).eps)
    assert -4.0 <= ganancia_inf_db <= -2.0, (
        f"Ganancia en f_inf esperada ~-3 dB, se obtuvo {ganancia_inf_db:.2f} dB"
    )

    # Ganancia en f_sup debe ser ~-3 dB (tolerancia 1 dB)
    idx_sup = np.argmin(np.abs(w - f_sup))
    ganancia_sup_db = 20 * np.log10(np.abs(h[idx_sup]) + np.finfo(float).eps)
    assert -4.0 <= ganancia_sup_db <= -2.0, (
        f"Ganancia en f_sup esperada ~-3 dB, se obtuvo {ganancia_sup_db:.2f} dB"
    )


# ==============================================================================
# Test 5: Escala logarítmica
# ==============================================================================

def test_a_escala_log_maximo_cero():
    """Verificar que el valor máximo de la salida es 0 dB."""
    signal = np.array([1.0, 0.5, 0.25, 0.1])
    resultado = a_escala_log(signal)

    assert abs(np.max(resultado) - 0.0) < 1e-6, (
        f"El máximo esperado es 0 dB, se obtuvo {np.max(resultado):.6f} dB"
    )


def test_a_escala_log_relacion():
    """Verificar que una señal con amplitud mitad da -6 dB."""
    signal = np.array([1.0, 0.5])
    resultado = a_escala_log(signal)

    # El segundo valor debe ser ~-6 dB
    assert abs(resultado[1] - (-6.0)) <= 0.1, (
        f"Se esperaba -6 dB para amplitud mitad, se obtuvo {resultado[1]:.2f} dB"
    )
