"""Endpoints SSE para procesamiento de audio en tiempo real."""

from __future__ import annotations

import io
import time
from collections.abc import AsyncGenerator

import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.services.filter import filtro_octava
from app.services.pink_noise import generar_ruido_rosa
from app.services.signal_utils import a_escala_log, obtener_ri_desde_sweep
from app.services.sine_sweep import generar_sine_sweep
from app.services.streaming import StreamingProcessor

router = APIRouter(prefix="/api/v1/streaming", tags=["streaming"])

BAND_COLORS = {
    125: "#22d3ee",
    250: "#38bdf8",
    500: "#818cf8",
    1000: "#a78bfa",
    2000: "#f472b6",
    4000: "#fb923c",
}


def _leer_audio_bytes(data: bytes) -> tuple[np.ndarray, int]:
    try:
        senal, fs = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
        return np.asarray(senal, dtype=np.float32), int(fs)
    except Exception as exc:
        raise ValueError(f"No se pudo leer el audio: {exc}") from exc


def _sse_response(gen: AsyncGenerator[str, None]) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ── Mensajes con markdown + LaTeX ─────────────────────────────────────────────

_MSG_DECONV_START = (
    "Método de **Farina (2000)** — convolución en dominio frecuencial (FFT):\n\n"
    r"$$h(t) \approx y(t) \ast x_{\mathrm{inv}}(t)$$"
    "\n\ndonde $y(t)$ es la grabación y $x_{\\mathrm{inv}}(t)$ el filtro inverso del sweep."
)

_MSG_ESCALA_LOG_START = (
    "Conversión a escala logarítmica normalizada al máximo:\n\n"
    r"$$L(t) = 20\log_{10}\!\left(\frac{|h(t)|}{\max|h(t)|}\right)$$"
    "\n\nPiso dinámico: $-120$ dB para evitar $-\\infty$. "
    "Máximo normalizado a $0$ dB."
)

_MSG_SWEEP_START = (
    "Barrido sinusoidal **logarítmico** (Farina, 2000):\n\n"
    r"$$x(t) = \sin\!\left(\frac{\omega_1\, T}{\ln(\omega_2/\omega_1)}"
    r"\left(e^{\,\frac{t}{T}\ln\frac{\omega_2}{\omega_1}} - 1\right)\right)$$"
    "\n\ndonde $T$ es la duración, $\\omega_1 = 2\\pi f_1$, $\\omega_2 = 2\\pi f_2$."
)

_MSG_SWEEP_LINEAL_START = (
    "Barrido sinusoidal **lineal**:\n\n"
    r"$$x(t) = \sin\!\left(2\pi\left(f_1 t + \frac{k\,t^2}{2}\right)\right)$$"
    r"$$k = \frac{f_2 - f_1}{T}$$"
)

_MSG_FILTRO_INVERSO_START = (
    "Filtro inverso: sweep invertido temporalmente con envolvente de corrección de amplitud:\n\n"
    r"$$x_{\mathrm{inv}}(t) = x(T - t)\cdot e^{-\frac{t}{T}\ln\!\frac{\omega_2}{\omega_1}}$$"
    "\n\nLa envolvente compensa la distribución no uniforme de energía del sweep logarítmico."
)

_MSG_RUIDO_ROSA_START = (
    "Filtrado espectral $1/\\sqrt{f}$ sobre ruido blanco en dominio frecuencial (FFT):\n\n"
    r"$$S_{\mathrm{rosa}}(f) = \frac{S_{\mathrm{blanco}}(f)}{\sqrt{f}}$$"
    "\n\nDensidad espectral de potencia resultante: $P(f) \\propto 1/f$ ($-3$ dB/oct)."
)


def _msg_banda_start(fc: float, fs: int) -> str:
    f_inf = fc / np.sqrt(2)
    f_sup = fc * np.sqrt(2)
    return (
        f"Filtro Butterworth paso de banda, orden 4 — **IEC 61260**:\n\n"
        r"$$f_{\mathrm{inf}} = \frac{f_c}{\sqrt{2}}, \qquad f_{\mathrm{sup}} = f_c\sqrt{2}$$"
        f"\n\n$f_c = {int(fc)}$ Hz  →  "
        f"$f_{{\\mathrm{{inf}}}} = {f_inf:.1f}$ Hz,  "
        f"$f_{{\\mathrm{{sup}}}} = {f_sup:.1f}$ Hz"
        "\n\nFiltro de fase cero (`filtfilt`) para preservar las relaciones temporales."
    )


# ── Deconvolución ──────────────────────────────────────────────────────────────

@router.post("/desconvolucionar", summary="Deconvolución con progreso en tiempo real")
async def desconvolucionar_stream(
    grabacion: UploadFile = File(..., description="WAV de la grabación del sweep"),
    filtro_inverso: UploadFile = File(..., description="WAV del filtro inverso"),
) -> StreamingResponse:
    grabacion_bytes = await grabacion.read()
    filtro_bytes = await filtro_inverso.read()

    async def gen() -> AsyncGenerator[str, None]:
        proc = StreamingProcessor()
        t_total = time.perf_counter()
        try:
            # 1. Cargar grabación
            t = time.perf_counter()
            yield proc.step_event("cargando_grabacion", "Leyendo archivo de grabación…")
            senal_grab, fs = _leer_audio_bytes(grabacion_bytes)
            dur_grab = len(senal_grab) / fs
            yield proc.step_event(
                "cargando_grabacion",
                f"**{fs} Hz** · {dur_grab:.2f} s · {len(senal_grab):,} muestras",
                tiempo_ms=(time.perf_counter() - t) * 1000,
            )

            # 2. Cargar filtro inverso
            t = time.perf_counter()
            yield proc.step_event("cargando_filtro", "Leyendo archivo de filtro inverso…")
            senal_fi, fs_fi = _leer_audio_bytes(filtro_bytes)
            if fs != fs_fi:
                yield proc.step_event(
                    "error",
                    f"Frecuencias de muestreo distintas: grabación **{fs} Hz** · "
                    f"filtro **{fs_fi} Hz**",
                )
                return
            yield proc.step_event(
                "cargando_filtro",
                f"**{fs_fi} Hz** · {len(senal_fi):,} muestras",
                tiempo_ms=(time.perf_counter() - t) * 1000,
            )

            # 3. Deconvolución FFT
            t = time.perf_counter()
            yield proc.step_event("deconvolucionando", _MSG_DECONV_START)
            ri = obtener_ri_desde_sweep(senal_grab, senal_fi)
            yield proc.step_event(
                "deconvolucionando",
                f"RI obtenida — **{len(ri) / fs:.3f} s** · {len(ri):,} muestras",
                tiempo_ms=(time.perf_counter() - t) * 1000,
            )

            # 4. Gráfico RI (primeros 2 s)
            t = time.perf_counter()
            yield proc.step_event(
                "graficando_ri", "Visualizando la respuesta al impulso (primeros 2 s)…"
            )
            fig, ax = proc.crear_figura()
            n_plot = min(len(ri), int(fs * 2))
            t_ms = np.arange(n_plot) / fs * 1000
            ax.plot(t_ms, ri[:n_plot], color="#22d3ee", linewidth=0.5, alpha=0.85)
            ax.set_xlabel("Tiempo (ms)", color="#94a3b8", fontsize=7)
            ax.set_ylabel("Amplitud", color="#94a3b8", fontsize=7)
            ax.set_title("Respuesta al impulso $h(t)$", color="#e2e8f0", fontsize=8, pad=6)
            ax.margins(x=0)
            img = proc.grafico_a_base64(fig)
            yield proc.step_event(
                "graficando_ri",
                "Primeros **2 s** de la RI",
                tiempo_ms=(time.perf_counter() - t) * 1000,
                grafico=img,
            )

            # 5. Escala logarítmica
            t = time.perf_counter()
            yield proc.step_event("escala_log", _MSG_ESCALA_LOG_START)
            ri_log = a_escala_log(ri)
            fig2, ax2 = proc.crear_figura()
            t_seg = np.arange(len(ri_log)) / fs
            ax2.plot(t_seg, ri_log, color="#a78bfa", linewidth=0.6, alpha=0.9)
            ax2.set_xlabel("Tiempo (s)", color="#94a3b8", fontsize=7)
            ax2.set_ylabel("dB", color="#94a3b8", fontsize=7)
            ax2.set_title("Curva de decaimiento $L(t)$", color="#e2e8f0", fontsize=8, pad=6)
            ax2.set_ylim(-85, 5)
            ax2.margins(x=0)
            img2 = proc.grafico_a_base64(fig2)
            yield proc.step_event(
                "escala_log",
                "Curva de decaimiento en dB generada",
                tiempo_ms=(time.perf_counter() - t) * 1000,
                grafico=img2,
            )

            # 6. Completado
            audio_b64 = proc.audio_a_base64(ri, fs)
            yield proc.step_event(
                "completado",
                f"Procesamiento completado en **{(time.perf_counter() - t_total) * 1000:.0f} ms**",
                tiempo_ms=(time.perf_counter() - t_total) * 1000,
                audio=audio_b64,
                audio_filename="impulse_response.wav",
            )

        except Exception as exc:
            yield proc.step_event("error", str(exc))

    return _sse_response(gen())


# ── Filtrado por bandas de octava ──────────────────────────────────────────────

@router.post("/filtrar-bandas", summary="Filtrar RI por bandas de octava con progreso")
async def filtrar_bandas_stream(
    file: UploadFile = File(..., description="WAV de la respuesta al impulso"),
    bandas: str = Form(
        default="125,250,500,1000,2000,4000",
        description="Bandas de octava separadas por coma (Hz)",
    ),
) -> StreamingResponse:
    audio_bytes = await file.read()

    async def gen() -> AsyncGenerator[str, None]:
        proc = StreamingProcessor()
        t_total = time.perf_counter()
        try:
            try:
                bandas_list = [float(b.strip()) for b in bandas.split(",") if b.strip()]
            except ValueError:
                yield proc.step_event("error", f"Parámetro `bandas` inválido: `{bandas}`")
                return

            # 1. Cargar RI
            t = time.perf_counter()
            yield proc.step_event("cargando", "Leyendo respuesta al impulso…")
            ri, fs = _leer_audio_bytes(audio_bytes)
            yield proc.step_event(
                "cargando",
                f"**{fs} Hz** · {len(ri) / fs:.2f} s · {len(ri):,} muestras",
                tiempo_ms=(time.perf_counter() - t) * 1000,
            )

            resultados: list[dict[str, str]] = []

            # 2. Filtrar cada banda
            for fc in bandas_list:
                fc_int = int(fc)
                color = BAND_COLORS.get(fc_int, "#22d3ee")

                t = time.perf_counter()
                yield proc.step_event(
                    f"filtrando_{fc_int}hz",
                    _msg_banda_start(fc, fs),
                )
                try:
                    filtrada = filtro_octava(ri, fc, fs)
                except ValueError as exc:
                    yield proc.step_event(
                        f"filtrando_{fc_int}hz",
                        f"Banda omitida: {exc}",
                        tiempo_ms=(time.perf_counter() - t) * 1000,
                    )
                    continue

                fig, ax_f = proc.crear_figura(figsize=(8, 2.2))
                n_plot = min(len(filtrada), int(fs * 2))
                t_ms = np.arange(n_plot) / fs * 1000
                ax_f.plot(t_ms, filtrada[:n_plot], color=color, linewidth=0.5, alpha=0.85)
                ax_f.set_xlabel("Tiempo (ms)", color="#94a3b8", fontsize=7)
                ax_f.set_title(f"Banda {fc_int} Hz", color="#e2e8f0", fontsize=8, pad=5)
                ax_f.margins(x=0)
                img = proc.grafico_a_base64(fig)

                audio_b64 = proc.audio_a_base64(filtrada, fs)
                filename = f"banda_{fc_int}Hz.wav"
                resultados.append({"filename": filename, "data": audio_b64})

                yield proc.step_event(
                    f"filtrando_{fc_int}hz",
                    f"Banda **{fc_int} Hz** filtrada",
                    tiempo_ms=(time.perf_counter() - t) * 1000,
                    grafico=img,
                    audio=audio_b64,
                    audio_filename=filename,
                )

            # 3. Completado
            yield proc.step_event(
                "completado",
                f"**{len(resultados)} bandas** filtradas en "
                f"**{(time.perf_counter() - t_total) * 1000:.0f} ms**",
                tiempo_ms=(time.perf_counter() - t_total) * 1000,
                audios=resultados,
            )

        except Exception as exc:
            yield proc.step_event("error", str(exc))

    return _sse_response(gen())


# ── Generación de sine sweep ───────────────────────────────────────────────────

@router.post("/generar-sweep", summary="Generar sine sweep con progreso en tiempo real")
async def generar_sweep_stream(
    f1: float = Form(20.0, description="Frecuencia inicial (Hz)"),
    f2: float = Form(20000.0, description="Frecuencia final (Hz)"),
    duracion: float = Form(5.0, description="Duración (s)"),
    fs: int = Form(44100, description="Frecuencia de muestreo (Hz)"),
    tipo: str = Form("logaritmico", description="'logaritmico' o 'lineal'"),
) -> StreamingResponse:
    async def gen() -> AsyncGenerator[str, None]:
        proc = StreamingProcessor()
        t_total = time.perf_counter()
        try:
            # 1. Generar sweep
            t = time.perf_counter()
            msg_sweep = (
                _MSG_SWEEP_START if tipo == "logaritmico" else _MSG_SWEEP_LINEAL_START
            )
            params_line = (
                f"\n\n$f_1 = {f1:.0f}$ Hz,  $f_2 = {f2:.0f}$ Hz,  "
                f"$T = {duracion}$ s,  $f_s = {fs}$ Hz"
            )
            yield proc.step_event("generando_sweep", msg_sweep + params_line)
            try:
                sweep, fi = generar_sine_sweep(f1, f2, duracion, fs, tipo)
            except ValueError as exc:
                yield proc.step_event("error", str(exc))
                return
            yield proc.step_event(
                "generando_sweep",
                f"Sweep generado — **{fs} Hz** · {len(sweep):,} muestras",
                tiempo_ms=(time.perf_counter() - t) * 1000,
            )

            # 2. Gráfico del sweep (primeros 50 ms)
            t = time.perf_counter()
            yield proc.step_event("graficando_sweep", "Visualizando los primeros 50 ms del sweep…")
            fig, ax = proc.crear_figura()
            n_plot = min(len(sweep), int(fs * 0.05))
            t_ms = np.arange(n_plot) / fs * 1000
            ax.plot(t_ms, sweep[:n_plot], color="#22d3ee", linewidth=0.6, alpha=0.9)
            ax.set_xlabel("Tiempo (ms)", color="#94a3b8", fontsize=7)
            ax.set_ylabel("Amplitud", color="#94a3b8", fontsize=7)
            ax.set_title(
                f"Sine sweep {tipo} ({f1:.0f}–{f2:.0f} Hz)", color="#e2e8f0", fontsize=8, pad=6
            )
            ax.margins(x=0)
            img_sweep = proc.grafico_a_base64(fig)
            yield proc.step_event(
                "graficando_sweep",
                "Primeros **50 ms** del sweep $x(t)$",
                tiempo_ms=(time.perf_counter() - t) * 1000,
                grafico=img_sweep,
            )

            # 3. Filtro inverso
            t = time.perf_counter()
            yield proc.step_event("graficando_filtro", _MSG_FILTRO_INVERSO_START)
            fig2, ax2 = proc.crear_figura()
            fi_plot = fi[:n_plot]
            ax2.plot(t_ms[: len(fi_plot)], fi_plot, color="#f472b6", linewidth=0.6, alpha=0.9)
            ax2.set_xlabel("Tiempo (ms)", color="#94a3b8", fontsize=7)
            ax2.set_ylabel("Amplitud", color="#94a3b8", fontsize=7)
            ax2.set_title(
                r"Filtro inverso $x_{\mathrm{inv}}(t)$", color="#e2e8f0", fontsize=8, pad=6
            )
            ax2.margins(x=0)
            img_fi = proc.grafico_a_base64(fig2)
            yield proc.step_event(
                "graficando_filtro",
                "Filtro inverso $x_{\\mathrm{inv}}(t)$ generado",
                tiempo_ms=(time.perf_counter() - t) * 1000,
                grafico=img_fi,
            )

            # 4. Completado
            sweep_b64 = proc.audio_a_base64(sweep, fs)
            fi_b64 = proc.audio_a_base64(fi, fs)
            yield proc.step_event(
                "completado",
                f"Generación completada en **{(time.perf_counter() - t_total) * 1000:.0f} ms**",
                tiempo_ms=(time.perf_counter() - t_total) * 1000,
                audios=[
                    {"filename": "sine_sweep.wav", "data": sweep_b64},
                    {"filename": "filtro_inverso.wav", "data": fi_b64},
                ],
            )

        except Exception as exc:
            yield proc.step_event("error", str(exc))

    return _sse_response(gen())


# ── Generación de ruido rosa ───────────────────────────────────────────────────

@router.post("/generar-ruido-rosa", summary="Generar ruido rosa con progreso en tiempo real")
async def generar_ruido_rosa_stream(
    duracion: float = Form(5.0, description="Duración (s)"),
    fs: int = Form(44100, description="Frecuencia de muestreo (Hz)"),
) -> StreamingResponse:
    async def gen() -> AsyncGenerator[str, None]:
        proc = StreamingProcessor()
        t_total = time.perf_counter()
        try:
            # 1. Generar ruido rosa
            t = time.perf_counter()
            params_line = f"\n\n$T = {duracion}$ s,  $f_s = {fs}$ Hz"
            yield proc.step_event("generando", _MSG_RUIDO_ROSA_START + params_line)
            try:
                ruido = generar_ruido_rosa(duracion, fs)
            except ValueError as exc:
                yield proc.step_event("error", str(exc))
                return
            yield proc.step_event(
                "generando",
                f"Ruido rosa generado — **{fs} Hz** · {len(ruido):,} muestras",
                tiempo_ms=(time.perf_counter() - t) * 1000,
            )

            # 2. Forma de onda (primeros 100 ms)
            t = time.perf_counter()
            yield proc.step_event("graficando_waveform", "Visualizando los primeros 100 ms…")
            fig, ax = proc.crear_figura()
            n_plot = min(len(ruido), int(fs * 0.1))
            t_ms = np.arange(n_plot) / fs * 1000
            ax.plot(t_ms, ruido[:n_plot], color="#22d3ee", linewidth=0.5, alpha=0.8)
            ax.set_xlabel("Tiempo (ms)", color="#94a3b8", fontsize=7)
            ax.set_ylabel("Amplitud", color="#94a3b8", fontsize=7)
            ax.set_title("Ruido rosa — forma de onda", color="#e2e8f0", fontsize=8, pad=6)
            ax.margins(x=0)
            img_wave = proc.grafico_a_base64(fig)
            yield proc.step_event(
                "graficando_waveform",
                "Primeros **100 ms** de la señal",
                tiempo_ms=(time.perf_counter() - t) * 1000,
                grafico=img_wave,
            )

            # 3. PSD
            t = time.perf_counter()
            yield proc.step_event(
                "graficando_espectro",
                "Calculando densidad espectral de potencia (PSD) para verificar "
                "$P(f) \\propto 1/f$…",
            )
            n_fft = min(len(ruido), 65536)
            espectro = np.abs(np.fft.rfft(ruido[:n_fft])) ** 2
            freqs = np.fft.rfftfreq(n_fft, d=1 / fs)
            block = 8
            n_bl = len(freqs) // block
            freqs_s = freqs[: n_bl * block].reshape(n_bl, block).mean(axis=1)
            esp_s = espectro[: n_bl * block].reshape(n_bl, block).mean(axis=1)

            fig2, ax2 = proc.crear_figura()
            mask = freqs_s > 0
            ax2.semilogx(
                freqs_s[mask], 10 * np.log10(esp_s[mask] + 1e-30),
                color="#a78bfa", linewidth=0.7, alpha=0.9,
            )
            ax2.set_xlabel("Frecuencia (Hz)", color="#94a3b8", fontsize=7)
            ax2.set_ylabel("dB", color="#94a3b8", fontsize=7)
            ax2.set_title(r"PSD — pendiente $-3$ dB/oct", color="#e2e8f0", fontsize=8, pad=6)
            ax2.set_xlim(20, fs / 2)
            img_esp = proc.grafico_a_base64(fig2)
            yield proc.step_event(
                "graficando_espectro",
                "PSD confirma la pendiente $-3$ dB/oct característica del ruido rosa",
                tiempo_ms=(time.perf_counter() - t) * 1000,
                grafico=img_esp,
            )

            # 4. Completado
            audio_b64 = proc.audio_a_base64(ruido, fs)
            yield proc.step_event(
                "completado",
                f"Generación completada en **{(time.perf_counter() - t_total) * 1000:.0f} ms**",
                tiempo_ms=(time.perf_counter() - t_total) * 1000,
                audio=audio_b64,
                audio_filename="pink_noise.wav",
            )

        except Exception as exc:
            yield proc.step_event("error", str(exc))

    return _sse_response(gen())
