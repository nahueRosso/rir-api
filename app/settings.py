"""Configuracion central de la aplicacion."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RIR-API"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    model_config = SettingsConfigDict(env_prefix="RIR_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
