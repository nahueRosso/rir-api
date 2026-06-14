"""RIR-API - Room Impulse Response API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import acoustics, generation, health, processing, streaming
from app.schemas.common import AppInfoResponse
from app.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "API para generacion de senales, procesamiento de respuestas al impulso "
        "y analisis acustico segun ISO 3382."
    ),
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(generation.router)
app.include_router(processing.router)
app.include_router(acoustics.router)
app.include_router(streaming.router)


@app.get("/", response_model=AppInfoResponse, tags=["root"], summary="Informacion basica de la API")
async def root() -> AppInfoResponse:
    return AppInfoResponse(
        name=settings.app_name,
        version=settings.app_version,
        description="Room Impulse Response API",
        docs="/docs",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.reload)
