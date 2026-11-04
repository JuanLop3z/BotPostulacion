# Instalación y operación

## Variables

`scripts/setup.py` crea `.env`, instala los paquetes fijados por `backend/requirements.lock` y
`frontend/package-lock.json`, y aplica Alembic. Python 3.12+; Node.js 22+. En Windows no hace
falta activar entornos ni cambiar ExecutionPolicy.

`DATABASE_URL` local puede apuntar a SQLite; Compose fuerza PostgreSQL y `INLINE_TASKS=false`.
`SECRET_KEY` cifra los CV: conserva una copia privada; cambiarla hace ilegibles los CV antiguos
sin una migración de cifrado. Las contraseñas de BD deben estar
codificadas para URL si se configuran caracteres reservados. El script genera valores URL-safe.

## Modos de ejecución

Local: SQLite y tareas FastAPI en segundo plano con `INLINE_TASKS=true`. Reiniciar la API
interrumpe esas tareas; este modo es para desarrollo y uso individual.

Compose: PostgreSQL/Redis persistentes, API, worker Celery con dos procesos y un scheduler.
APScheduler revisa cada cinco minutos y respeta el intervalo de búsqueda del espacio personal (mínimo seis horas).
Programa Remotive y demo; cada portal Greenhouse requiere elegir explícitamente su token.
No se inicia ninguna búsqueda programada mientras la automatización esté parada.

API/OpenAPI: `/docs`. Endpoints bajo `/api/v1`, sin login ni cabeceras Authorization.
`CORS_ORIGINS` acepta los alias `localhost` y `127.0.0.1` para el mismo puerto local,
incluyendo instalaciones con un `.env` anterior que sólo tenía uno de ellos.
`GET /workspace` devuelve el espacio personal persistente. «Mi perfil» admite entrada manual sin CV.
`GET /health` comprueba el proceso y `/api/v1/health/ready` comprueba la conexión de BD.

La migración conserva los datos existentes. Al abrir esta versión por primera vez reutiliza el
propietario más antiguo de la instalación y lo vincula de forma persistente al espacio local.
Si una instalación antigua contiene varios propietarios, `LOCAL_USER_ID` permite elegir uno
antes de la primera apertura; no se mezclan sus datos. Después de vincularlo, la elección se conserva.
Las cuentas antiguas dejan de tener rutas de acceso y el scheduler sólo procesa el espacio seleccionado.

## Datos de contexto

Los cuatro archivos opcionales de `context/` (`candidate_context.md`,
`custom_instructions.md`, `job_preferences.yaml` y `application_rules.yaml`) contienen
datos locales y quedan excluidos de Git. Una copia nueva usa contexto vacío y las
preferencias/reglas por defecto si no existen esos archivos. La primera lectura crea
una versión del espacio personal. Editar desde el dashboard guarda en BD y conserva el historial.
Después de cambiar archivos en disco, `POST /api/v1/context/reload` importa una nueva versión.
No se sobrescriben los archivos en disco al editar desde la interfaz.

El parser de contexto reconoce declaraciones como `Habilidades confirmadas: Python, Java` o
`Años de experiencia: 5`; las incorpora como propuestas no verificadas. Verifica cada dato en
la interfaz y vuelve a revisar el perfil. Texto libre privado no se incorpora a cartas.
Las exclusiones operativas deben configurarse en los campos estructurados de preferencias.

## Pruebas de navegador

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD/storage/browsers"
.venv\Scripts\python.exe -m playwright install chromium
$env:RUN_BROWSER_TESTS = '1'
.venv\Scripts\python.exe -m pytest backend/tests/test_automation.py -m browser -q
```

El navegador de pruebas sólo permite localhost y bloquea conexiones salientes y WebSockets.
No guarda sesiones de portales reales. No es un conector de envío a LinkedIn u otros ATS.

## Retención, eliminación y copias

`RETENTION_DAYS` (90 por defecto) elimina documentos CV originales y eventos antiguos mediante
la tarea diaria `autojob.retention`; puede invocarse con `celery -A app.workers.tasks:celery_app call autojob.retention`.
Los perfiles, contextos y candidaturas permanecen para mantener seguimiento; `DELETE /api/v1/workspace`
borra los datos de ese espacio por cascada, elimina sus CV cifrados y crea uno vacío. Esta operación no tiene deshacer.
Respaldar volúmenes PostgreSQL y storage junto con SECRET_KEY para restaurar documentos.

## Diagnóstico

- 409 al enviar: revisa bloqueos, aprobación, cuotas, parada o snapshots antiguos; regenera y aprueba.
- Fuente real sin envío: abre el enlace original; es una capacidad declarada del conector.
- 422 de contexto: revisa YAML y esquema; no se aceptan claves desconocidas.
- Búsqueda fallida: consulta eventos/tarea y token Greenhouse. No hay fallback a datos ficticios.
- PDF sin texto: aplica OCR fuera del sistema y vuelve a cargarlo; no se finge una extracción.
- Worker no disponible: verifica Redis y logs de Celery; en local usa INLINE_TASKS=true.
