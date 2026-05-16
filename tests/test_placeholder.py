"""Tests minimos para el milestone 0."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_docs_endpoint_is_available():
    response = client.get("/docs")
    assert response.status_code == 200


def test_generation_router_is_registered():
    response = client.post(
        "/api/v1/generation/pink-noise",
        json={"duracion": 0.01, "fs": 8000, "guardar_audio": False, "max_points": 20},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tipo"] == "pink_noise"
    assert data["fs"] == 8000
    assert data["audio"]["cantidad_muestras"] == 80
    assert len(data["audio"]["amplitude"]) <= 20
    assert data["audio"]["samples_reducidos"] is True


def test_sine_sweep_accepts_tipo_barrido():
    response = client.post(
        "/api/v1/generation/sine-sweep",
        json={
            "frecuencia_inicial": 20,
            "frecuencia_final": 1000,
            "duracion": 0.01,
            "fs": 8000,
            "tipo_barrido": "lineal",
            "guardar_audio": False,
            "guardar_filtro_inverso": False,
            "max_points": 20,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tipo"] == "sine_sweep"
    assert data["tipo_barrido"] == "lineal"
    assert len(data["sweep"]["amplitude"]) <= 20
