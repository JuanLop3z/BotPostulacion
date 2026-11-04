# Requisitos y decisiones de alcance

| Área del archivo maestro | Entrega verificable |
|---|---|
| Fundamentos | Monorepo Python/Next, Compose, SQLAlchemy, Alembic, configuración |
| CV | PDF/DOCX/TXT, procedencia, corrección, revisión, versiones, cifrado |
| Contexto obligatorio | Cuatro archivos, versiones por cuenta, propuestas verificables |
| Ofertas | Greenhouse y Remotive reales, capacidades, normalización, dedupe, caché |
| Portales asistidos | LinkedIn/Computrabajo por texto y enlace del usuario, matching, carta y registro manual |
| Matching | Seis pesos, reglas, keywords, embeddings opcionales reales y pgvector |
| Candidaturas | Resumen/carta/CV TXT verificables, aprobación y pendientes |
| Automatización | Proveedor demo, idempotencia, cuotas, guard, parada, navegador controlado |
| Seguimiento | Máquina de estados, eventos, registro manual, CSV, dashboard |
| Ejecución periódica | Celery + APScheduler, backoff de lectura limitado |
| Calidad | Pytest, Ruff, Mypy, typecheck/build frontend, CI |

La configuración actual sigue la petición de uso personal: el dashboard abre directamente,
sin registro, contraseña ni JWT. Se conserva el propietario interno para mantener el historial
y los controles de idempotencia; «Mi perfil» permite proporcionar datos manualmente sin CV.

## Decisiones

Se priorizó el MVP útil y honesto solicitado en los criterios de aceptación. El envío autorizado
se demuestra mediante un proveedor de pruebas local. No se inventaron integraciones de envío
a portales sin autorización de empleador ni datos profesionales de ejemplo para el usuario.
La composición de servicios está en un orquestador explícito y tareas pequeñas, sin agentes
autónomos con acceso arbitrario a herramientas.

No se implementaron OCR, envío real ATS, email/Slack/webhooks, lectura de respuestas de empleadores,
aprendizaje automático de decisiones, CV PDF maquetado, índices ANN de dimensión fija ni inspección
universal de formularios externos. Preferencias de sectores/moneda deseada se conservan, pero sólo
criterios estructurados disponibles en el feed intervienen en el matching. Las instrucciones
libres no son un lenguaje de reglas general; las exclusiones deben ir en preferencias estructuradas.

Para evolución: un proveedor real de envío necesita contrato de autorización, esquema completo
de preguntas, clave idempotente y reconciliación de recepción. Nuevas fuentes deben declarar
capacidades y tener mocks de errores/rate-limit, sin fallback silencioso a demo.
