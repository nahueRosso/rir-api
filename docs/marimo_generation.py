import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import sounddevice as sd

    def generar_ruido_rosa(duracion: float, fs: int) -> np.ndarray:
        """Genera ruido rosa aproximado mediante filtrado espectral 1/sqrt(f)."""
        if duracion <= 0:
            raise ValueError("duracion debe ser positiva")
        if fs <= 0:
            raise ValueError("fs debe ser positivo")

        n_samples = int(duracion * fs)
        if n_samples <= 0:
            raise ValueError("duracion * fs debe generar al menos una muestra")

        ruido_blanco = np.random.randn(n_samples)
        espectro = np.fft.rfft(ruido_blanco)
        freqs = np.fft.rfftfreq(n_samples, d=1 / fs)

        filtro = np.ones_like(freqs)
        filtro[1:] = 1 / np.sqrt(freqs[1:])

        espectro_rosa = espectro * filtro
        ruido_rosa = np.fft.irfft(espectro_rosa, n=n_samples)

        max_abs = np.max(np.abs(ruido_rosa))
        if max_abs > 0:
            ruido_rosa = ruido_rosa / max_abs

        return ruido_rosa.astype(np.float32)

    def generar_sine_sweep(
        f1: float, f2: float, duracion: float, fs: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Genera un sine sweep logaritmico y su filtro inverso.

        Parameters
        ----------
        f1 : float
            Frecuencia inicial en Hz.
        f2 : float
            Frecuencia final en Hz.
        duracion : float
            Duracion del sweep en segundos.
        fs : int
            Frecuencia de muestreo en Hz.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Tupla con (sweep, filtro_inverso), ambos normalizados.
        """

        # 1. Crear el vector de tiempo
        muestras = int(duracion * fs)
        t = np.arange(muestras) / fs

        # 2. Convertir frecuencias a radianes/segundo
        w1 = 2 * np.pi * f1
        w2 = 2 * np.pi * f2

        # 3. Calcular la tasa de barrido logarítmico
        R = np.log(w2 / w1)

        # 4. Generar la señal del Sine Sweep
        fase = (w1 * duracion / R) * (np.exp((t / duracion) * R) - 1)
        sweep = np.sin(fase)

        # 5. Generar envolvente y filtro inverso
        envolvente = np.exp((-t / duracion) * R)
        filtro_inverso = sweep[::-1] * envolvente

        # 6. Normalización (escalar para que el valor máximo absoluto sea 1.0)
        sweep_norm = sweep / np.max(np.abs(sweep))
        filtro_inverso_norm = filtro_inverso / np.max(np.abs(filtro_inverso))

        return sweep_norm, filtro_inverso_norm

    return generar_ruido_rosa, generar_sine_sweep, np, sd


@app.cell
def _(np, sd):
    def reproducir_y_grabar(
        signal: np.ndarray, fs: int, duracion_grabacion: float
    ) -> np.ndarray:
        """Reproduce una senal y graba simultaneamente.

        La funcion agrega un silencio inicial de 0.5 segundos para compensar
        parte de la latencia del sistema de audio.

        Parameters
        ----------
        signal : np.ndarray
            Senal a reproducir. Puede ser un array 1D (mono) o 2D con forma
            ``(muestras, canales)``.
        fs : int
            Frecuencia de muestreo en Hz.
        duracion_grabacion : float
            Duracion total de la grabacion en segundos. Debe ser mayor o igual
            a la duracion de la senal reproducida.

        Returns
        -------
        np.ndarray
            Senal grabada. Si la entrada es mono, retorna un array 1D. Si la
            entrada es multicanal, retorna un array 2D.

        Raises
        ------
        ValueError
            Si la senal tiene una forma invalida, esta vacia, ``fs`` no es
            positivo o ``duracion_grabacion`` es insuficiente.
        RuntimeError
            Si no hay dispositivos de audio disponibles o si ocurre un error
            durante la reproduccion/grabacion.
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
            raise ValueError(
                "duracion_grabacion debe ser mayor o igual a la duracion de la senal"
            )

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
            raise RuntimeError(
                f"No fue posible acceder a los dispositivos de audio: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Error durante la reproduccion y grabacion de audio: {exc}"
            ) from exc

        grabacion_array = np.asarray(grabacion, dtype=np.float32)
        if is_mono:
            return grabacion_array[:, 0]
        return grabacion_array


    return (reproducir_y_grabar,)


@app.cell
def _(sd):
    default_device = sd.default.device
    dispositivos = sd.query_devices()

    print("Dispositivo por defecto (input, output):", default_device)
    print(dispositivos)

    return default_device, dispositivos


@app.cell
def _(generar_ruido_rosa):
    fs_ruido = 44100
    duracion_ruido = 2.0
    ruido_rosa = generar_ruido_rosa(duracion_ruido, fs_ruido)

    print(f"Ruido rosa generado: {ruido_rosa.shape[0]} muestras")

    return duracion_ruido, fs_ruido, ruido_rosa


@app.cell
def _(fs_ruido, ruido_rosa):
    from pathlib import Path

    import soundfile as sf

    repo_root = Path.cwd()
    if not (repo_root / "pyproject.toml").exists():
        candidatos = [repo_root, *repo_root.parents]
        repo_root = next(
            (path for path in candidatos if (path / "pyproject.toml").exists()),
            repo_root,
        )

    ruta_ruido = repo_root / "data" / "ruido_rosa.wav"
    ruta_ruido.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(ruta_ruido), ruido_rosa, fs_ruido)
    print(f"Ruido rosa guardado en {ruta_ruido}")

    return ruta_ruido


@app.cell
def _(fs_ruido, ruido_rosa, sd):
    ganancia = 0.2
    print(f"Reproduciendo ruido rosa a ganancia {ganancia:.1f}")
    sd.play(ganancia * ruido_rosa, fs_ruido, blocking=True)

    return ganancia


@app.cell
def _(generar_sine_sweep, reproducir_y_grabar):
    fs = 44100
    duracion_sweep = 1.0
    duracion_grabacion = 2.0
    sweep, filtro_inverso = generar_sine_sweep(20, 20000, duracion_sweep, fs)
    grabacion = reproducir_y_grabar(sweep, fs, duracion_grabacion)

    return filtro_inverso, fs, grabacion, sweep


@app.cell
def _(fs, grabacion):
    from pathlib import Path

    import soundfile as sf

    repo_root = Path.cwd()
    if not (repo_root / "pyproject.toml").exists():
        candidatos = [repo_root, *repo_root.parents]
        repo_root = next(
            (path for path in candidatos if (path / "pyproject.toml").exists()),
            repo_root,
        )

    ruta_salida = repo_root / "data" / "grabacion.wav"
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(ruta_salida), grabacion, fs)
    print(f"Grabacion guardada en {ruta_salida}")

    return ruta_salida, sf


if __name__ == "__main__":
    app.run()
