from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AppInfoResponse(BaseModel):
    name: str
    version: str
    description: str
    docs: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class PlaceholderResponse(BaseModel):
    message: str = "falta implementar logica"


class PlaceholderRequest(BaseModel):
    param: dict[str, Any] = {}
