"""Configuracion central de la aplicacion."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RIR-API"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://rirapp.com",
        "https://www.rirapp.com",
    ]

    model_config = SettingsConfigDict(env_prefix="RIR_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
