# RIR-API

API REST para procesamiento y analisis de respuestas al impulso segun la norma ISO 3382.

<!-- Badges -->
![CI](../../actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Descripción

RIR-API es una API REST construida con FastAPI para generar señales de
excitación, procesar respuestas al impulso y calcular parámetros acústicos
según ISO 3382. El proyecto se organiza en capas para separar validación,
lógica de negocio y exposición HTTP desde el inicio del desarrollo.

Este repositorio corresponde al plano de arquitectura del sistema. En `M0`
se define la estructura final de routers, schemas y services que se completará
en `M1`, `M2` y `M3`, manteniendo desde ahora una base ejecutable, testeable
y apta para trabajo colaborativo.


## Integrantes

| Nombre completo | Legajo | Rol |
| --- | --- | --- |
| Nahuel Rojo | 77440 | Arquitectura / API |
| Lautaro Ibáñez | 74262 | Generación de señales |
| Tomás Travaglini | 75714 | Procesamiento de RI |
| Lorenzo D'Uva | 78176 | Testing / CI / Documentación |

## Requisitos previos

- Python 3.12 o superior
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes y entornos virtuales)

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/nahueRosso/rir-api.git
cd rir-api

# Crear entorno virtual e instalar dependencias
uv venv
uv pip install -e ".[dev]"
```

## Ejecución

```bash
# Levantar el entorno interactivo de marimo
uv run start-marimo
```

Alternativa:

```bash
# Abrir el notebook directamente con marimo
marimo edit docs/marimo_acoustics.py
```

Si necesitás seguir levantando la API REST:

```bash
uvicorn app.main:app --reload
```

La API queda disponible en:

- `http://localhost:8000/`
- `http://localhost:8000/health`
- `http://localhost:8000/docs`

## Testing y calidad

```bash
# Ejecutar todos los tests
uv run pytest -v

# Verificar estilo de codigo
uv run ruff check app/ tests/
```

## Estructura del proyecto

```text
rir-api/
├── pyproject.toml                # Dependencias y configuración del proyecto
├── README.md                     # Documentación principal y diagrama de arquitectura
├── LICENSE                       # Licencia del repositorio
├── app/
│   ├── __init__.py
│   ├── main.py                   # Punto de entrada FastAPI
│   ├── settings.py               # Configuración central con pydantic-settings
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py             # Endpoints base: / y /health
│   │   ├── generation.py         # Endpoints de M1
│   │   ├── processing.py         # Endpoints de M2
│   │   └── acoustics.py          # Endpoints de M3
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py             # Schemas compartidos
│   │   ├── generation.py         # Request/response de generación
│   │   ├── processing.py         # Request/response de procesamiento
│   │   └── acoustics.py          # Request/response de análisis acústico
│   └── services/
│       ├── __init__.py
│       ├── pink_noise.py         # Lógica DSP de ruido rosa
│       ├── sine_sweep.py         # Lógica DSP de sweep logarítmico
│       ├── signal_utils.py       # Utilidades de audio y RI
│       ├── filter.py             # Filtrado por bandas de octava
│       └── acoustic_parameters.py# Cálculo de parámetros ISO 3382
├── tests/
│   ├── test_api.py               # Tests de endpoints base
│   └── test_placeholder.py       # Test mínimo que debe pasar en M0
├── docs/                         # Documentación adicional
├── data/
│   └── .gitkeep                  # Directorio reservado para datos locales
└── .github/workflows/ci.yml      # Pipeline de CI
```

## Arquitectura

La API se separa en tres capas:

- `routers`: reciben requests HTTP, documentan endpoints y delegan.
- `schemas`: validan requests y responses con Pydantic.
- `services`: concentran la lógica de negocio y DSP.

Los módulos principales quedan divididos por dominio:

- `generation`: generación de ruido rosa, sweep y flujo de reproducción/grabación.
- `processing`: carga de audio, obtención de RI, filtrado por octava,
  escala logarítmica y síntesis de RI.
- `acoustics`: integral de Schroeder, regresión lineal y cálculo de parámetros acústicos.

## Diagrama de arquitectura

```mermaid
flowchart LR
    CLIENTE[Cliente HTTP]
    API[FastAPI app]

    CLIENTE --> API

    subgraph BASE[Base]
        RH[health router]
        SCHC[schemas.common]
        RH --> SCHC
    end

    subgraph GEN[Generation]
        RG[generation router]
        SCHG[schemas.generation]
        SG[services.pink_noise<br/>services.sine_sweep]
        G1[generar_ruido_rosa]
        G2[generar_sine_sweep]
        G3[reproducir_y_grabar]

        RG --> SCHG
        RG --> SG
        SG --> G1
        SG --> G2
        SG --> G3
    end

    subgraph PROC[Processing]
        RP[processing router]
        SCHP[schemas.processing]
        SP[services.signal_utils<br/>services.filter]
        P1[cargar_audio]
        P2[obtener_ri_desde_sweep]
        P3[filtro_octava]
        P4[a_escala_log]
        P5[sintetizar_ri]

        RP --> SCHP
        RP --> SP
        SP --> P1
        SP --> P2
        SP --> P3
        SP --> P4
        SP --> P5
    end

    subgraph AC[Acoustics]
        RA[acoustics router]
        SCHA[schemas.acoustics]
        SA[services.acoustic_parameters]
        A1[integral_schroeder]
        A2[regresion_lineal]
        A3[calcular_parametros_acusticos]
        A4[metodo_lundeby]

        RA --> SCHA
        RA --> SA
        SA --> A1
        SA --> A2
        SA --> A3
        SA --> A4
    end

    API --> RH
    API --> RG
    API --> RP
    API --> RA

    classDef entry fill:#1f2937,stroke:#111827,color:#ffffff
    classDef router fill:#dbeafe,stroke:#2563eb,color:#0f172a
    classDef schema fill:#dcfce7,stroke:#16a34a,color:#052e16
    classDef service fill:#fef3c7,stroke:#d97706,color:#451a03
    classDef fn fill:#f3f4f6,stroke:#6b7280,color:#111827

    class CLIENTE,API entry
    class RH,RG,RP,RA router
    class SCHC,SCHG,SCHP,SCHA schema
    class SG,SP,SA service
    class G1,G2,G3,P1,P2,P3,P4,P5,A1,A2,A3,A4 fn
```

## Flujo de datos

1. El cliente envía un request HTTP a un endpoint.
2. FastAPI valida el cuerpo y los parámetros usando un schema Pydantic.
3. El router delega la operación al service correspondiente.
4. El service produce datos procesados.
5. El router devuelve una respuesta JSON validada por un schema de salida.

**Inputs esperados:** archivos de audio, arrays numéricos y configuraciones de medición.  
**Outputs esperados:** respuestas al impulso, curvas de decaimiento y parámetros acústicos calculados.

## Endpoints planificados

### Base
- `GET /`
- `GET /health`

### M1 — Generation
- `POST /api/v1/generation/pink-noise`
- `POST /api/v1/generation/sine-sweep`
- `POST /api/v1/generation/play-record`

### M2 — Processing
- `POST /api/v1/processing/load-audio`
- `POST /api/v1/processing/impulse-response-from-sweep`
- `POST /api/v1/processing/octave-filter`
- `POST /api/v1/processing/log-scale`
- `POST /api/v1/processing/synthesize-ri`

### M3 — Acoustics
- `POST /api/v1/acoustics/schroeder`
- `POST /api/v1/acoustics/linear-regression`
- `POST /api/v1/acoustics/parameters`
- `POST /api/v1/acoustics/lundeby`

## Branching strategy

- `main` protegida — merge solo vía pull request.
- Cada desarrollo nuevo sale de una rama `feature/nombre-descriptivo`.
- Commits siguiendo Conventional Commits:
  - `feat(routers): add generation placeholder endpoints`
  - `docs(readme): document architecture and milestones`
  - `test(api): add milestone 0 placeholder test`

## Estado de los milestones

| Milestone | Estado | Fecha |
| --- | --- | --- |
| M0 — Arquitectura | En curso | 28 Abr 2026 |
| M1 — Generación de señales | Pendiente | 19 May 2026 |
| M2 — Procesamiento de RI | Pendiente | 16 Jun 2026 |
| M3 — Producto final | Pendiente | 7 Jul 2026 |

