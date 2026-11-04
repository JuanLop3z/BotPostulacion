# AutoJob AI

Asistente privado de búsqueda laboral. Carga un CV real, revisa sus hechos, añade contexto,
consulta vacantes, compara requisitos y prepara candidaturas con trazabilidad.
El repositorio contiene backend, dashboard, migraciones, workers, configuración,
pruebas y documentación. Es un MVP para uso personal local; no es un servicio
de postulaciones automáticas desplegado.

## Código y datos locales

Se comparte el código, las pruebas y `.env.example`, con valores de ejemplo.
El `.env` real, los archivos personales de `context/`, bases de datos, CV,
capturas y reportes de `storage/` quedan excluidos de Git.

Una copia nueva inicia sin tu perfil ni preferencias personales. Puedes
configurarlos desde el dashboard; los archivos de `context/` son opcionales y
la aplicación utiliza valores por defecto cuando no existen. No copies secretos,
credenciales de portales ni datos personales a archivos que vayas a versionar.

## Inicio local en Windows

Requiere Python 3.12+ y Node.js 22+. Desde la raíz:

```powershell
python scripts/setup.py
```

El script instala dependencias, crea `.env` con secretos aleatorios y aplica migraciones.
No sobrescribe un `.env` existente. Usa SQLite para trabajar sin Docker/Redis.

Después, haz doble clic en `iniciar.bat` o ejecuta desde PowerShell:

```powershell
.\iniciar.bat
```

Abre dos ventanas con los logs del backend y el frontend, prepara la configuración y aplica
migraciones antes del arranque. Espera a que ambas estén listas y abre http://localhost:3000.
Para detenerlos, pulsa `Ctrl+C` en cada ventana. Puedes ejecutarlo desde cualquier carpeta;
el `.bat` usa la ubicación del proyecto. `iniciar.bat --check` comprueba las dependencias sin
arrancar servidores. Si ya tienes instancias ejecutándose, detenlas antes de volver a iniciarlas.

También puedes iniciarlos manualmente. Terminal 1:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2:

```powershell
cd frontend
npm.cmd run dev
```

Abre [dashboard](http://localhost:3000) y [API documentada](http://localhost:8000/docs).
`npm.cmd` evita depender de la política de ejecución de scripts de PowerShell.
Para Linux/macOS, usa `.venv/bin/python` y `npm`.

## Inicio con Docker Compose

```powershell
python scripts/setup.py --env-only
docker compose up --build
```

El paso `--env-only` prepara secretos aleatorios sin instalar dependencias del backend ni frontend.
Se levantan PostgreSQL con pgvector, Redis, API, Celery, scheduler y Next.js.
Sólo los puertos locales 3000 y 8000 se publican. Las migraciones se ejecutan al arrancar la API.
No se requiere una clave de IA para el flujo local determinista.

## Primer recorrido

1. Abre el dashboard directamente. En «Mi perfil», introduce tus datos o carga tu CV PDF, DOCX o TXT (máximo 10 MB).
2. Corrige el perfil extraído. El parser conserva evidencia y deja desconocidos los campos que no puede demostrar.
3. Edita contexto y reglas. «Incorporar contexto» propone hechos explícitos; confirma cada propuesta y revisa el perfil.
4. Busca en Greenhouse indicando el token del portal corporativo (por ejemplo `stripe`), Remotive o «Proveedor de pruebas local».
5. Revisa puntuación, brechas y bloqueos. Un requisito excluyente pendiente impide elegibilidad aunque la puntuación sea alta.
6. Prepara y aprueba una candidatura. Habilita la automatización para probar el envío **local de demostración**.
7. Para una vacante real, abre el portal y completa allí la postulación. Registra por separado el envío y su confirmación.

Para LinkedIn, Computrabajo u otro portal, ve a **Oportunidades → Importar oferta**. Pega el
enlace, cargo, empresa y texto publicado (también sirve el texto de una alerta por correo).
Puedes completar modalidad, ubicación, salario y requisitos cuando aparezcan en la oferta.
La app guarda y analiza el contenido que aportas, detecta duplicados y prepara la candidatura.
En la ficha de una oferta importada, **Completar datos** permite añadir información publicada
después. Si cambian los datos de una candidatura preparada, hay que regenerarla y revisarla.
Desde **Candidaturas** puedes copiar la carta, descargar el CV y abrir la oferta original
para postularte en tu navegador. No se solicitan contraseñas ni cookies de los portales.

El sistema arranca con automatización parada, revisión individual obligatoria y sin consentimiento
para servicios de IA ni envío de datos a terceros. Nunca envía candidaturas reales con los conectores incluidos.
Las vacantes demo y sus confirmaciones están identificadas como simulación.

## Alcance implementado

- Espacio personal local que se abre directamente, sin registro, contraseña ni sesión.
- CV cifrados en disco, perfiles/contextos versionados, hechos con procedencia y revisión explícita.
- Fuentes reales Greenhouse y Remotive con capacidades y caché compartida de seis horas.
- Importación asistida de LinkedIn, Computrabajo y otros portales desde texto y enlace aportados por el usuario.
- Deduplicación, matching ponderado explicable, requisitos obligatorios independientes y caché por versión.
- IA opcional con Ollama o gateway JSON, consentimiento, grounding y embeddings reales opcionales con pgvector.
- Cartas y CV de texto derivados exclusivamente de hechos verificados, preguntas pendientes sin respuestas inventadas.
- Máquina de estados, aprobación, cuotas diarias/semanales, idempotencia, auditoría, parada y evidencia demo.
- Dashboard responsive, filtros, registro manual de postulaciones, reportes CSV y eventos.
- Celery, APScheduler, reintentos limitados de lectura y retención de documentos/eventos antiguos.
- Playwright para formularios de prueba locales con aislamiento de red y detección de intervención humana.

## Comprobaciones

```powershell
.venv\Scripts\python.exe -m pytest backend/tests -q
.venv\Scripts\python.exe -m ruff check backend
.venv\Scripts\python.exe -m mypy backend/app
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

Las pruebas no gastan créditos ni envían postulaciones reales. Las dos pruebas de concurrencia
requieren `TEST_DATABASE_URL` con PostgreSQL y se omiten localmente si no está disponible.
El test de navegador requiere Chromium;
el smoke de lectura real es optativo: `.venv\Scripts\python.exe scripts/smoke_greenhouse.py --board stripe`.
Consulta [validación](docs/validation.md) para resultados y límites del entorno.

## Documentación

- [Instalación y operación](docs/setup.md)
- [Arquitectura y decisiones](docs/architecture.md)
- [Fuentes y sus límites reales](docs/integrations.md)
- [Seguridad y datos personales](docs/security.md)
- [IA y embeddings opcionales](docs/ai-gateway.md)
- [Cobertura de requisitos y evolución](docs/requirements.md)

Este MVP está preparado para uso personal local. OCR, envío a ATS reales, notificaciones externas,
aprendizaje de decisiones y generación de CV maquetado quedan como extensiones explícitas.
