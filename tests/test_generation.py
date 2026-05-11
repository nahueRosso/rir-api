"""Tests requeridos para Milestone 1: Generacion de senales."""

import numpy as np
import pytest
from scipy.signal import welch, fftconvolve, spectrogram
from unittest.mock import patch, MagicMock

from app.services.pink_noise import generar_ruido_rosa
from app.services.sine_sweep import generar_sine_sweep


# ==============================================================================
# Test 1: Espectro del ruido rosa
# ==============================================================================

def test_ruido_rosa_espectro():
    """
    Verifica que el espectro del ruido rosa tiene una pendiente
    de aproximadamente -3 dB/octava.

    Procedimiento:
    1. Genera ruido rosa de 10 segundos a 44100 Hz.
    2. Calcula la PSD usando el metodo de Welch.
    3. Calcula la pendiente en dB/octava entre 100 Hz y 10000 Hz.
    4. Verifica que la pendiente este entre -4 y -2 dB/octava.
    """
    duracion = 10.0
    fs = 44100

    ruido = generar_ruido_rosa(duracion, fs)

    # Calcular PSD con metodo de Welch
    frecuencias, psd = welch(ruido, fs=fs, nperseg=4096)

    # Filtrar el rango de frecuencias de interes (100 Hz a 10000 Hz)
    mask = (frecuencias >= 100) & (frecuencias <= 10000)
    freq_rango = frecuencias[mask]
    psd_rango = psd[mask]

    # Convertir PSD a dB
    psd_db = 10 * np.log10(psd_rango)

    # Convertir frecuencias a escala logaritmica (octavas)
    freq_log = np.log2(freq_rango)

    # Calcular la pendiente con regresion lineal (polyfit grado 1)
    pendiente, _ = np.polyfit(freq_log, psd_db, 1)

    # Verificar que la pendiente esta entre -4 y -2 dB/octava
    assert -4.0 <= pendiente <= -2.0, (
        f"Pendiente esperada entre -4 y -2 dB/octava, se obtuvo {pendiente:.2f}"
    )


# ==============================================================================
# Test 2: Rango de frecuencias del sine sweep
# ==============================================================================

def test_sine_sweep_rango_frecuencias():
    """
    Verifica que el sine sweep cubre el rango de frecuencias
    especificado de f1 a f2.

    Procedimiento:
    1. Genera un sweep de 20 Hz a 20000 Hz de 5 segundos a 44100 Hz.
    2. Calcula el espectrograma de la senal.
    3. Verifica que hay energia significativa en f1 y f2.
    4. Verifica que la frecuencia instantanea crece monotonicamente.
    """
    f1 = 20.0
    f2 = 20000.0
    duracion = 5.0
    fs = 44100

    sweep, _ = generar_sine_sweep(f1, f2, duracion, fs)

    # Calcular espectrograma
    frecuencias, tiempos, Sxx = spectrogram(sweep, fs=fs, nperseg=1024)

    # Para cada instante de tiempo, encontrar la frecuencia con mayor energia
    freq_instantanea = frecuencias[np.argmax(Sxx, axis=0)]

    # Verificar energia en frecuencia inicial (primeros 10% del sweep)
    n_inicial = int(len(tiempos) * 0.10)
    freq_inicio_promedio = np.mean(freq_instantanea[:n_inicial])
    assert freq_inicio_promedio < 200, (
        f"Se esperaba frecuencia inicial cercana a {f1} Hz, "
        f"se obtuvo {freq_inicio_promedio:.1f} Hz"
    )

    # Verificar energia en frecuencia final (ultimos 10% del sweep)
    n_final = int(len(tiempos) * 0.10)
    freq_fin_promedio = np.mean(freq_instantanea[-n_final:])
    assert freq_fin_promedio > 10000, (
        f"Se esperaba frecuencia final cercana a {f2} Hz, "
        f"se obtuvo {freq_fin_promedio:.1f} Hz"
    )

    # Verificar que la frecuencia instantanea crece monotonicamente
    # (se acepta una tolerancia del 5% de ventanas no monotónicas)
    diferencias = np.diff(freq_instantanea)
    proporcion_creciente = np.sum(diferencias >= 0) / len(diferencias)
    assert proporcion_creciente >= 0.95, (
        f"La frecuencia instantanea no crece monotonicamente "
        f"({proporcion_creciente*100:.1f}% de ventanas crecientes)"
    )


# ==============================================================================
# Test 3: Convolucion sweep * filtro inverso produce un impulso
# ==============================================================================

def test_sweep_convolucion_impulso():
    """
    Verifica que la convolucion del sweep con su filtro inverso
    produce una aproximacion a un impulso.

    Procedimiento:
    1. Genera sweep y filtro inverso.
    2. Calcula la convolucion via FFT.
    3. Encuentra el pico maximo.
    4. Verifica que la energia del pico es al menos 40 dB superior
       a la energia promedio del resto de la senal.
    """
    f1 = 20.0
    f2 = 20000.0
    duracion = 5.0
    fs = 44100

    sweep, filtro_inverso = generar_sine_sweep(f1, f2, duracion, fs)

    # Convolucionar sweep con filtro inverso via FFT
    resultado = fftconvolve(sweep, filtro_inverso)

    # Encontrar el indice del pico maximo
    idx_pico = np.argmax(np.abs(resultado))
    valor_pico = np.abs(resultado[idx_pico])

    # Excluir una ventana de 100 muestras alrededor del pico
    ventana = 100
    mascara = np.ones(len(resultado), dtype=bool)
    mascara[max(0, idx_pico - ventana): idx_pico + ventana] = False
    resto = resultado[mascara]

    # Calcular energia del pico vs energia promedio del resto
    energia_pico = valor_pico ** 2
    energia_promedio_resto = np.mean(resto ** 2)

    # Evitar log de cero
    assert energia_promedio_resto > 0, "La energia del resto es cero"

    diferencia_db = 10 * np.log10(energia_pico / energia_promedio_resto)

    assert diferencia_db >= 40, (
        f"Se esperaba que el pico supere al resto en al menos 40 dB, "
        f"se obtuvo {diferencia_db:.1f} dB"
    )


# ==============================================================================
# Test 4: Reproduccion y grabacion
# ==============================================================================

def test_reproducir_y_grabar_forma():
    """
    Verifica que la funcion maneja correctamente senales mono y estereo,
    y que lanza una excepcion si no hay dispositivo de audio disponible.

    Nota: este test usa un mock de sounddevice para poder correr en CI
    sin hardware de audio. Para probarlo con hardware real, ejecutar:
        pytest tests/test_generation.py::test_reproducir_y_grabar_forma -v
    """
    from app.services.play_record import reproducir_y_grabar

    fs = 44100
    duracion_grabacion = 3.0
    n_muestras_esperadas = int(duracion_grabacion * fs)

    # --- Caso 1: senal mono (1D) ---
    signal_mono = np.zeros(fs * 2)  # 2 segundos de silencio
    grabacion_simulada = np.zeros((n_muestras_esperadas, 1), dtype=np.float32)

    with patch("sounddevice.check_input_settings"), \
         patch("sounddevice.check_output_settings"), \
         patch("sounddevice.playrec", return_value=grabacion_simulada), \
         patch("sounddevice.wait"):
        resultado = reproducir_y_grabar(signal_mono, fs, duracion_grabacion)

    assert resultado.ndim in (1, 2), "El resultado debe ser mono o estereo"
    assert abs(len(resultado) - n_muestras_esperadas) <= n_muestras_esperadas * 0.01, (
        f"Duracion incorrecta: se esperaban ~{n_muestras_esperadas} muestras, "
        f"se obtuvieron {len(resultado)}"
    )

    # --- Caso 2: senal estereo (2D) ---
    signal_estereo = np.zeros((fs * 2, 2))  # 2 segundos estereo
    grabacion_simulada_estereo = np.zeros((n_muestras_esperadas, 2), dtype=np.float32)

    with patch("sounddevice.check_input_settings"), \
         patch("sounddevice.check_output_settings"), \
         patch("sounddevice.playrec", return_value=grabacion_simulada_estereo), \
         patch("sounddevice.wait"):
        resultado_estereo = reproducir_y_grabar(signal_estereo, fs, duracion_grabacion)

    assert resultado_estereo.ndim in (1, 2), "El resultado estereo debe ser array valido"

    # --- Caso 3: sin dispositivo de audio disponible ---
    with patch("sounddevice.check_input_settings", side_effect=Exception("No audio device")):
        with pytest.raises(RuntimeError):
            reproducir_y_grabar(signal_mono, fs, duracion_grabacion)