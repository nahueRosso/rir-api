from datetime import datetime

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
