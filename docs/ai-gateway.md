# IA opcional y embeddings

El funcionamiento base usa extracción conservadora, reglas y keywords sin llamadas de IA.
No se presenta este modo como un análisis LLM. Cartas locales son plantillas basadas en hechos.
Los costos aparecen «sin medición» cuando el proveedor no publica costos: no se inventan precios.

## Ollama real

Instala Ollama, descarga un modelo de generación y uno de embeddings y configura `.env`:

```dotenv
LLM_PROVIDER=ollama
LLM_ENDPOINT=http://localhost:11434
LLM_MODEL=llama3.2
EMBEDDING_MODEL=nomic-embed-text
ENABLE_EMBEDDINGS=true
```

Ejecuta `ollama pull llama3.2` y `ollama pull nomic-embed-text`. Con Docker Desktop, usa
`http://host.docker.internal:11434` para acceder al Ollama del host. No viene incluido como
servicio ni se descargan modelos grandes sin configuración explícita.

Activa `llm_consent` en tus reglas personales antes de subir un CV para análisis IA.
El proveedor utiliza `/api/generate`, JSON Schema, sin streaming; valida la salida con Pydantic
y contrasta hechos con el texto original. Hallazgos adicionales quedan como inferencias pendientes.
`/api/embed` devuelve vectores reales, almacenados en caché por cuenta y modelo. Sólo se envía
texto técnico del perfil y la vacante; contexto privado/contacto no se necesitan para similitud.

Fuentes: [generate de Ollama](https://docs.ollama.com/api/generate),
[embed de Ollama](https://docs.ollama.com/api/embed),
[salidas estructuradas](https://docs.ollama.com/capabilities/structured-outputs).
Las pruebas usan respuestas simuladas HTTP; no certifican la calidad de un modelo descargado.

## Gateway propio desacoplado

`LLM_PROVIDER=generic` espera un servidor JSON propio, **no** es una URL directamente compatible
con OpenAI ni otros proveedores comerciales. `LLM_ENDPOINT` se configura por el operador, nunca por
una vacante. HTTPS remoto obligatorio, sin redirecciones; la clave viaja en Authorization.

- `POST /analyze-cv`: recibe `{document,response_schema,instructions}` y devuelve `{profile,usage?}`.
- `POST /embed`: recibe `{text}` y devuelve `{embedding:number[],usage?}`.
- Vectores no vacíos, finitos, máximo 4096 dimensiones; dimensiones consistentes por modelo.

Puede implementarse un nuevo `AIProvider` para otro proveedor. No se distribuye un gateway
ficticio ni se reclama compatibilidad comercial no probada. Los errores se muestran sin payloads
ni tokens. Cuando IA está habilitada y falla, se informa del fallo; no se factura ni muestra éxito ficticio.
