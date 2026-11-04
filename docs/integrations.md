# Integraciones

| Fuente | Búsqueda real | Preparar local | Enviar desde app | Consultar recepción |
|---|---|---|---|---|
| Greenhouse Job Board | Sí, por token corporativo | Sí | No | No |
| Remotive | Sí, feed público | Sí | No | No |
| Demo | Vacantes sintéticas explícitas | Sí | Sólo simulación local | Sólo simulación local |
| LinkedIn | Texto y enlace aportados por el usuario | Sí | Manual en el portal | Registro declarado por el usuario |
| Computrabajo | Texto y enlace aportados por el usuario | Sí | Manual en el portal | Registro declarado por el usuario |
| Otro portal | Texto y enlace aportados por el usuario | Sí | Manual en el portal | Registro declarado por el usuario |

## Greenhouse

GET público `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`, sin credenciales.
El token es el identificador del portal de una empresa, no una API key. Se limita a letras,
números, guion y guion bajo; URLs externas nunca controlan el host de consulta.
Se conservan descripción, enlace original y requisitos detectables. El proveedor no garantiza
datos salariales o preguntas completas en el feed: cualquier envío futuro debe validar el
formulario y todos sus requisitos.

La API de envío requiere una credencial del empleador. Tener una cuenta de candidato no otorga
esa autorización. El flujo incluido abre el enlace y registra lo informado por el usuario.
Referencia: [documentación oficial Job Board API](https://docs.greenhouse.io/job-board.html).

## Remotive

GET fijo `https://remotive.com/api/remote-jobs`. Descarga feed completo, aplica consultas localmente
y comparte caché seis horas. El dashboard conserva «Remotive» y el enlace original como atribución.
El salario textual ambiguo permanece en descripción; no se inventan moneda ni periodicidad.
No existe aquí una integración de envío.

Usar esta integración como herramienta privada local. Los términos del feed requieren atribución,
prohíben redistribución a otros portales y restringen listados utilizados para captar registros.
Revisar términos antes de desplegar públicamente; la autorización del feed no implica la del ATS.
Referencia: [API oficial de Remotive](https://github.com/remotive-com/remote-jobs-api/blob/main/README.md).

## LinkedIn y Computrabajo: importación asistida

En **Oportunidades → Importar oferta**, el usuario pega el texto publicado y un enlace de
la vacante. El formulario también acepta contenido de una alerta recibida por correo; no
hay acceso automático al buzón. Se indican cargo y empresa y, cuando estén publicados,
ubicación, modalidad, salario, periodicidad y requisitos obligatorios. Para un salario fijo,
se repite el importe en ambos campos del rango. Los datos ausentes permanecen desconocidos.

`POST /api/v1/jobs/import` valida el dominio del portal, normaliza el texto y calcula el matching
con el perfil/contexto actuales. LinkedIn conserva el ID de la vacante incluso con enlaces
de búsqueda `currentJobId`. Computrabajo ignora parámetros de seguimiento para la identidad.
Una oferta repetida devuelve la ya guardada sin crear otra candidatura ni sobrescribir su contenido.
**Completar datos** usa `PUT /api/v1/jobs/{id}/import` para editar explícitamente la misma vacante.
Recalcula la compatibilidad y revoca la aprobación de candidaturas preparadas, que deben regenerarse.
El portal/ID de la vacante se mantienen y no se altera la oferta de una candidatura ya enviada.

Las fuentes asistidas declaran `search=false` y `submit=false`; no aparecen como fuentes de
búsqueda automática. El proceso no visita el enlace, ejecuta scripts del contenido, solicita
contraseñas, importa cookies ni controla una sesión del portal. El usuario inicia sesión en
su navegador habitual. El matching con IA opcional respeta el consentimiento ya configurado.

Desde **Candidaturas**, el usuario puede copiar la carta, descargar el CV de texto y abrir el
enlace original. Tras completar personalmente el envío, registra el resultado. La evidencia
conserva `reported_by_user=true` y `platform_verified=false`: no se presenta como confirmación
obtenida por una integración. Tampoco se permite el envío desde `/submit` para estas fuentes.

Referencias: [política oficial de LinkedIn](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software)
y [condiciones de Computrabajo](https://co.computrabajo.com/avisolegal/).

## Otros conectores automáticos

Indeed, elempleo, Get on Board, Wellfound y Remote OK no tienen conectores automáticos
implementados. Las importaciones asistidas no se publicitan como APIs ni usan scrapers de fallback. Pueden incorporarse
mediante `JobSourceAdapter` después de verificar API/feed, condiciones, límites y autorización.

Los fallos transitorios de lectura permiten backoff limitado; autenticación, CAPTCHA, permisos
y errores definitivos no se reintentan automáticamente. No se reintenta un envío ambiguo sin
reconciliar evidencia con el proveedor.
