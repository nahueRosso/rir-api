# AI\_LOG.md — Registro de uso de IA en el desarrollo de RIR-API

Este documento reúne los registros de consultas a herramientas de IA (Claude \- Gemini- Chat GPT) realizadas por el equipo durante el desarrollo del proyecto RIR-API (github.com/nahueRosso/rir-api, deploy en rirapp.com). El objetivo es dejar constancia transparente de en qué momentos se usó IA como apoyo — para resolver dudas puntuales, explorar alternativas técnicas o depurar errores — y aclarar que el diseño, la implementación y las decisiones finales fueron tomadas por el equipo. En ningún caso la IA definió la arquitectura, escribió el código de producción o tomó decisiones de diseño; se usó como herramienta de consulta, de la misma manera que se usa documentación oficial o foros técnicos.

El registro se organiza en tres partes: un log cronológico detallado sobre la integración de streaming frontend/backend, un compilado temático de consultas sobre arquitectura, procesamiento de señales y flujo de trabajo en Git, y por último la corrección de bugs puntuales junto con la documentación del README.

---

## Parte 1 — Registro cronológico: integración streaming frontend/backend

Trabajo sobre la conexión entre el hook `useStreamingProcessor` (front, Next.js) y los endpoints de streaming del backend (FastAPI, `app/routers/streaming.py` \+ `app/services/streaming.py`).

### 2026-06-11

Se empezó a analizar cómo el front debía consumir los endpoints que devuelven progreso en tiempo real (`/desconvolucionar`, `/filtrar-bandas`, etc). El backend manda eventos con formato `data: {...}\n\n` (SSE manual sobre `StreamingResponse`, no `EventSource` nativo, porque el body se manda por POST con FormData). Del lado del front había que leer el stream a mano con `fetch` \+ `ReadableStream`, ya que `EventSource` del navegador solo soporta GET.

### 2026-06-12

Se escribió una primera versión de `useStreamingProcessor.ts` que lee el reader del body, decodifica con `TextDecoder` y separa por `\n\n`. Funcionaba en pruebas manuales cortas, pero con la deconvolución (archivos más grandes, más eventos) empezaron a aparecer steps pisados o duplicados en la UI.

### 2026-06-13

Se encontró el bug: se separaba por `\n\n` directo sobre el buffer parcial, y como los chunks del stream no respetan el límite de los eventos, a veces un `data: {...}` quedaba cortado a la mitad entre dos `read()`. Se cambió la lógica a separar por `\n` simple, guardando la última línea (posiblemente incompleta) en el buffer y reprocesándola en la vuelta siguiente. Cada línea completa que empieza con `data:`  se parsea individualmente.

### 2026-06-16

Duda para consultar / anotada para no perderla: por qué el test de pytest `test_streaming.py::TestFormatSse` no tiraba error pero el string no matcheaba en el assert. Se determinó que `format_sse` devuelve el JSON con `ensure_ascii=False` (para no romper tildes/ñ en los mensajes), y el test comparaba contra un string con caracteres escapados a mano. El problema era del test, no del código de la función.

### 2026-06-17

Se terminaron de escribir los tests de `StreamingProcessor.step_event` en el backend (`api/tests/test_streaming.py`): casos mínimos (solo step \+ message), con `tiempo_ms` redondeado a 1 decimal, con gráfico/audio/audios opcionales, y con kwargs extra mezclados en el payload. Estos tests sirvieron como referencia para tipar `StreamStep` en el front.

### 2026-06-18

Al correr `pytest` localmente aparecía `ModuleNotFoundError: soundfile` por estar usando un venv distinto al activado (hay dos: el del proyecto y el del sistema). Se perdió tiempo hasta detectar que se estaba corriendo `python -m pytest` con el intérprete equivocado. Queda anotado: activar siempre `api/.venv` antes de correr tests.

### 2026-06-19

Se agregó el manejo de `step === "error"` en el hook: si el backend manda un evento con ese step, se setea `error` en el estado del hook y se frena el loading, en vez de esperar a que se cierre la conexión sola. Antes el error quedaba silencioso y la UI se quedaba con el spinner infinito.

### 2026-06-20

Se cableó `StreamingPanel.tsx` para que renderice la lista completa de `steps` acumulados (con `StreamingStep.tsx` por cada uno) en vez de mostrar solo el último. La consigna pedía ver el progreso paso a paso, no solo el resultado final, por lo que se expuso `steps` completo desde el hook además de `lastStep`.

### 2026-06-23

En producción (atrás de Nginx) el streaming no actualizaba en tiempo real: llegaba todo junto al final, como una respuesta normal. Era buffering de Nginx sobre la respuesta chunked. No hubo que tocar nada del front; se resolvió agregando `X-Accel-Buffering: no` en la respuesta del backend.

### 2026-06-24

Se escribieron tests nuevos en `test_streaming.py` para las funciones auxiliares del router (`_leer_audio_bytes` y `_sanear_nan`), generando un WAV sintético en memoria con `soundfile` (una RI exponencial con ruido, T60 configurable) para no depender de archivos de audio reales en el repo.

### 2026-06-25

`_sanear_nan` rompía un test porque el backend calcula parámetros acústicos por banda y algunas bandas dan `NaN` (señal muy corta para esa banda). El test esperaba que esos NaN se conviertan en `null` antes de mandarse como JSON (si no, `JSON.parse` del lado del front explota, porque `NaN` no es JSON válido). Se terminó de entender el motivo real de esa función.

### 2026-06-26

Se ajustó `ProcessDialog.tsx` para usar `isCompleted` del hook y así decidir cuándo cerrar el modal automáticamente o habilitar el botón de "cerrar". Antes dependía de mirar `lastStep?.step === "completado"` desde afuera, lo cual duplicaba lógica que ya vivía en el hook.

### 2026-06-27

Se corrió toda la suite de `test_streaming.py` en limpio antes de la entrega parcial: 14 tests entre `TestFormatSse`, `TestStepEvent` y las funciones del router, todos en verde. Queda pendiente para más adelante escribir tests del lado del front para el hook (todavía no hay test runner configurado en `web/`; por ahora se probó a mano en el navegador).

---

## Parte 2 — Consultas temáticas: arquitectura, procesamiento de señales, entorno y Git

### Organización del código en FastAPI

**Contexto:** había dudas sobre cómo modularizar la API a medida que crecía. **Consulta a IA:** se preguntó por patrones habituales de organización en proyectos FastAPI. **Decisión del equipo:** se optó por separar responsabilidades en capas propias del proyecto — routers para los endpoints, schemas (Pydantic) para validación de datos, y services para la lógica de negocio — evaluando que esa división era la que mejor se adaptaba a cómo veníamos trabajando en equipo.

### Generación de sine sweep y deconvolución (ISO 3382\)

**Contexto:** para el procesamiento acústico del proyecto (extracción de la respuesta al impulso de una sala a partir de un sweep grabado) había que asegurarse de entender bien los fundamentos antes de programarlos. **Consulta a IA:** se consultaron dudas conceptuales sobre el barrido de frecuencia logarítmico y su relación matemática con la deconvolución para obtener la RI, comparando con la bibliografía de la materia. **Decisión del equipo:** la implementación del algoritmo (generación del sweep, filtro inverso, deconvolución) se programó y ajustó por el equipo, validando los resultados contra referencias externas (ver validación con datos de OpenAIR).

### Transmisión de datos en tiempo real (SSE)

**Contexto:** se necesitaba mandar al cliente el estado del procesamiento (progreso, métricas parciales) de forma asíncrona. **Consulta a IA:** se compararon alternativas (Server-Sent Events vs WebSockets) para entender ventajas y limitaciones de cada una. **Decisión del equipo:** se eligió SSE por ser más simple para un flujo unidireccional servidor→cliente y no requerir manejo de conexión bidireccional; la implementación concreta del endpoint y del consumo en el front se hizo dentro del equipo (ver Parte 1 para el detalle de bugs y decisiones tomadas en esa implementación).

### Errores de import y entorno virtual

**Contexto:** aparecía `ModuleNotFoundError` al ejecutar la app, por problemas con las rutas de importación entre routers y services al reorganizar carpetas. **Consulta a IA:** se preguntó cómo funciona la resolución de paths en Python y cómo FastAPI localiza los paquetes internos. **Decisión del equipo:** se revisó y corrigió la estructura de imports del proyecto en base a eso.

### Gestión de dependencias

**Contexto:** hacía falta un manejo más prolijo y reproducible del entorno virtual entre los tres integrantes. **Consulta a IA:** se preguntó por buenas prácticas de gestión de paquetes en Python. **Decisión del equipo:** se adoptó `uv` para acelerar la instalación y mantener consistencia del entorno entre las máquinas del equipo.

### Flujo de trabajo en Git

**Contexto:** al ser un proyecto grupal con tres integrantes trabajando sobre el mismo repo, hacía falta un flujo claro para no pisarse el código. **Consulta a IA:** se consultaron los comandos y el orden de pasos para clonar, sincronizar cambios de compañeros antes de subir los propios, y hacer Pull Requests de forma segura. **Decisión del equipo:** se acordó un flujo de trabajo con ramas por feature y PR obligatorio antes de mergear a main.

### Integración continua

**Contexto:** se quería automatizar la corrida de tests en cada cambio subido al repo. **Consulta a IA:** se preguntó cómo configurar integración continua sobre GitHub. **Decisión del equipo:** se armó un workflow de GitHub Actions propio, ajustado a la estructura de tests del proyecto (pytest en el backend).

---

## Parte 3 — Corrección de bugs puntuales y documentación

### Corrección del bug en `test_sintetizar_ri_decaimiento`

**Contexto:** el test fallaba en la presentación con el error "T60 esperado: 2.00s, medido: 0.02s". Había que encontrar y corregir el problema antes de la re-entrega.

**Diagnóstico propio:** se identificó que la curva de energía muestra a muestra tenía fluctuaciones de ruido que tocaban \-60 dB antes de que la señal realmente decayera hasta ese nivel.

**Consulta a IA:** se consultaron alternativas para suavizar la curva antes de medir el T60 (`savgol_filter`, envolvente de Hilbert, promedio móvil).

**Decisión propia:** se probó cada alternativa corriendo el test y evaluando el resultado. Se eligió el promedio móvil con convolución porque es el concepto más directo y ya visto en la materia, no requiere elegir múltiples parámetros adicionales, y el test pasó con T60 medido ≈ 2.01s, dentro del ±10% de tolerancia:

ventana \= int(0.05 \* fs)  \# 50 ms

kernel \= np.ones(ventana) / ventana

energia\_suavizada \= np.convolve(energia, kernel, mode='same')

### Documentación del README

**Consulta a IA:** se consultó cómo referenciar imágenes con rutas relativas dentro del README, y cómo documentar endpoints junto con sus schemas de forma clara.

**Decisión propia:** los schemas se relevaron directamente desde el `/docs` de la API levantada localmente, verificando cada endpoint con "Try it out", y las descripciones se redactaron a partir de eso. Las imágenes de validación fueron capturadas directamente desde rirapp.com.

---

*Este registro documenta el uso de IA como herramienta de consulta y apoyo durante el desarrollo (dudas conceptuales, exploración de alternativas técnicas, debugging). Las decisiones de diseño, la implementación y la validación de resultados fueron responsabilidad del equipo.*  
