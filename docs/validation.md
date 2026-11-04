# Validación de la entrega

Comprobaciones realizadas en Windows, Python 3.13.7 y Node.js 22.18.0, el 30 de octubre de 2026.
La aplicación soporta Python 3.12+; CI y Docker usan 3.12.

| Comprobación | Resultado |
|---|---|
| Pytest backend con Chromium real activado | 173 aprobadas, 2 omitidas por requerir PostgreSQL |
| Ruff lint y formato backend | Correctos |
| Mypy backend | Sin errores en 57 archivos fuente |
| pip check | Sin dependencias rotas |
| Alembic upgrade head + check, SQLite | Correctos, sin diferencias de esquema |
| Next.js TypeScript y compilación de producción | Correctos |
| Prettier frontend | Correcto |
| Flujo UI real Chromium, escritorio y móvil390px | Correcto, sin errores JS ni overflow |
| Formulario localhost Playwright | Correcto; campos desconocidos y CAPTCHA bloquean |
| Greenhouse GET real, portal stripe | 737 vacantes recuperadas; cero candidaturas enviadas |
| Compose | YAML inspeccionado; servicios y dependencias definidos |

El recorrido UI comprueba apertura directa sin login ni tokens, entrada manual sin CV,
persistencia al recargar, carga TXT, corrección/revisión, contexto, reglas, búsqueda demo,
score, preparación, aprobación, envío demo, parada y vista móvil. Arranca una API y base
temporal aisladas y descarta los datos sintéticos al terminar; no modifica el espacio real.
La interfaz diferencia «0 reales · 1 de prueba».
El recorrido ampliado importa ofertas sintéticas de LinkedIn y Computrabajo, completa datos,
comprueba duplicados, copia la carta al portapapeles y registra un envío manual declarado.
No visita los portales; al sumar ese registro muestra «1 reales · 1 de prueba» dentro de la base temporal.
Capturas locales en `storage/reports/ui-*.png` (ignoradas por Git).

## Límites de lo comprobado

Docker no está instalado en este equipo: no se ejecutó `docker compose up` ni se arrancaron
PostgreSQL/Redis/Celery reales aquí. Se incluyen servicios CI para PostgreSQL y compilación
de imágenes, pero ese workflow todavía no se ha ejecutado en un repositorio remoto.
Las dos pruebas de concurrencia con locks reales se activan con `TEST_DATABASE_URL`.
La comprobación local de SQLite no demuestra garantías de concurrencia de PostgreSQL.

Ollama y el gateway se prueban con HTTP simulado y vectores controlados; no se descargó un
modelo ni se gastaron créditos. La consulta real de Greenhouse es de lectura. Remotive se
prueba con fixtures HTTP; no se afirma haber realizado un envío ni una consulta real a ese feed.

Starlette emite una advertencia de deprecación sobre su cliente de pruebas con HTTPX; la suite
actual pasa. No afecta al cliente HTTPX que utilizan los adaptadores ni a la API en ejecución.

## Reproducir

Desde la raíz, con dependencias instaladas:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD/storage/browsers"
$env:RUN_BROWSER_TESTS = '1'
.venv\Scripts\python.exe -m pytest backend/tests -q
.venv\Scripts\python.exe -m ruff check backend
.venv\Scripts\python.exe -m ruff format --check backend
.venv\Scripts\python.exe -m mypy backend/app
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

Para el smoke UI, inicia el frontend y ejecuta
`.venv\Scripts\python.exe frontend/scripts/smoke_ui.py`.
El script crea su propia API temporal y redirige las peticiones del navegador hacia ella.
Para concurrencia, apunta `TEST_DATABASE_URL` a una BD PostgreSQL desechable con pgvector;
las pruebas crean y eliminan esquemas aleatorios aislados en esa BD.
