"""Tests minimos para el milestone 0."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_docs_endpoint_is_available():
    response = client.get("/docs")
    assert response.status_code == 200


def test_generation_router_is_registered():
    """El endpoint devuelve un WAV binario (flujo directo, ver docstring del router)."""
    response = client.post(
        "/api/v1/generation/pink-noise",
        json={"duracion": 0.01, "fs": 8000},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"


def test_sine_sweep_accepts_tipo_barrido():
    """El endpoint devuelve un WAV binario (flujo directo, ver docstring del router)."""
    response = client.post(
        "/api/v1/generation/sine-sweep",
        json={
            "frecuencia_inicial": 20,
            "frecuencia_final": 1000,
            "duracion": 0.01,
            "fs": 8000,
            "tipo_barrido": "lineal",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content[:4] == b"RIFF"
