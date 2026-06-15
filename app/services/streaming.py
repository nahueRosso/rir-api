"""Utilidades para emitir eventos SSE durante el procesamiento de audio."""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime
from typing import Any

import numpy as np
import soundfile as sf
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


class StreamingProcessor:
    """Utilidades estáticas para formatear eventos SSE y convertir datos."""

    @staticmethod
    def format_sse(data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def step_event(
        step: str,
        message: str,
        tiempo_ms: float | None = None,
        grafico: str | None = None,
        audio: str | None = None,
        audio_filename: str | None = None,
        audios: list[dict[str, str]] | None = None,
        **extra: Any,
    ) -> str:
        payload: dict[str, Any] = {
            "step": step,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        if tiempo_ms is not None:
            payload["tiempo_ms"] = round(tiempo_ms, 1)
        if grafico is not None:
            payload["grafico"] = grafico
        if audio is not None:
            payload["audio"] = audio
        if audio_filename is not None:
            payload["audio_filename"] = audio_filename
        if audios is not None:
            payload["audios"] = audios
        payload.update(extra)
        return StreamingProcessor.format_sse(payload)

    @staticmethod
    def grafico_a_base64(fig: Figure) -> str:
        """Convierte una Figure de matplotlib a PNG base64 con fondo oscuro."""
        FigureCanvasAgg(fig)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=90, bbox_inches="tight",
                    facecolor="#0f172a", edgecolor="none")
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def audio_a_base64(senal: np.ndarray, fs: int) -> str:
        """Convierte un numpy array a WAV float32 en base64."""
        buf = io.BytesIO()
        sf.write(buf, senal.astype(np.float32), fs, format="WAV", subtype="FLOAT")
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def crear_figura(figsize: tuple[float, float] = (8, 2.5)) -> tuple[Figure, Any]:
        """Crea una figura con estilo oscuro consistente con el frontend."""
        fig = Figure(figsize=figsize, facecolor="#0f172a")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#0f172a")
        ax.tick_params(colors="#94a3b8", labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")
        ax.grid(True, color="#1e293b", linewidth=0.5)
        return fig, ax
