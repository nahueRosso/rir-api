"""Tests para los endpoints de la API (Milestone 3)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
