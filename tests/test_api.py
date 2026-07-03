"""Tests para los endpoints de la API (Milestone 3)."""

import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _wav_bytes(t60: float = 1.0, fs: int = 16000, duracion: float = 2.0) -> bytes:
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


class TestHealthEndpoint:
    """Tests para el endpoint /health."""

    def test_health_returns_200(self):
        """Verifica que /health responde con status 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy(self):
        """Verifica que el status es 'healthy'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_includes_version(self):
        """Verifica que la respuesta incluye la version."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data


class TestRootEndpoint:
    """Tests para el endpoint raiz /."""

    def test_root_returns_200(self):
        """Verifica que / responde con status 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_api_info(self):
        """Verifica que la raiz devuelve informacion de la API."""
        response = client.get("/")
        data = response.json()
        assert data["name"] == "RIR-API"
        assert "docs" in data


class TestAcousticsEndpoints:
    """Tests para los endpoints de /api/v1/acoustics."""

    def test_schroeder_endpoint(self):
        """Enviar un WAV y verificar la curva de Schroeder en dB."""
        files = {"file": ("ri.wav", _wav_bytes(), "audio/wav")}
        response = client.post("/api/v1/acoustics/schroeder", files=files)
        assert response.status_code == 200
        data = response.json()
        assert abs(data["edc_db"][0]) < 1e-3
        assert len(data["tiempo"]) == len(data["edc_db"])

    def test_smoothing_endpoint_hilbert(self):
        """Verifica el suavizado por defecto (envolvente de Hilbert)."""
        files = {"file": ("ri.wav", _wav_bytes(), "audio/wav")}
        response = client.post("/api/v1/acoustics/smoothing", files=files)
        assert response.status_code == 200
        data = response.json()
        assert all(v >= 0 for v in data["envolvente"])

    def test_linear_regression_endpoint(self):
        """Verifica la regresion lineal via JSON."""
        x = list(np.linspace(0, 4, 5))
        y = [2.0 * xi + 1.0 for xi in x]
        response = client.post(
            "/api/v1/acoustics/linear-regression", json={"x": x, "y": y}
        )
        assert response.status_code == 200
        data = response.json()
        assert abs(data["pendiente"] - 2.0) < 1e-6
        assert abs(data["r_cuadrado"] - 1.0) < 1e-6

    def test_parameters_endpoint(self):
        """Enviar un WAV a /api/v1/acoustics/parameters y verificar la respuesta."""
        files = {"file": ("ri.wav", _wav_bytes(t60=1.5), "audio/wav")}
        response = client.post("/api/v1/acoustics/parameters", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "T30" in data["parametros"]
        assert "1000" in data["parametros"]["T30"]

    def test_lundeby_endpoint(self):
        """Verifica que /api/v1/acoustics/lundeby responde con indice y ruido."""
        files = {"file": ("ri.wav", _wav_bytes(), "audio/wav")}
        response = client.post("/api/v1/acoustics/lundeby", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["indice_truncamiento"] > 0

    def test_invalid_file_returns_400(self):
        """Un archivo invalido (no WAV) debe retornar un error 4xx, no 500."""
        files = {"file": ("ri.txt", b"esto no es un wav", "text/plain")}
        response = client.post("/api/v1/acoustics/schroeder", files=files)
        assert response.status_code == 400
