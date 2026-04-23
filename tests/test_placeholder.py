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
        json={"param": {"duration": 1.0, "sample_rate": 44100}},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "falta implementar logica"
