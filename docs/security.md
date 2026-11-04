# Seguridad y privacidad

El sistema funciona como espacio personal local, sin login. Los puertos de Compose y el
lanzador se limitan a loopback. La API rechaza hosts y orígenes web ajenos a la configuración local.

- Un propietario interno persistente agrupa CV, contexto y candidaturas; no se piden credenciales
  ni se almacenan tokens de sesión en el navegador. Los IDs recibidos se comprueban contra ese propietario.
- CV originales cifrados con Fernet; claves derivadas de SECRET_KEY. Tokens/model keys sólo entorno.
- Perfiles/contexto contienen datos personales en PostgreSQL/SQLite: el cifrado de CV no equivale
  a cifrado completo de BD. Protege disco, volúmenes y copias. No se almacenan credenciales ATS.
- PDF/DOCX/TXT se validan por formato, tamaño y contenido; DOCX tiene límite de expansión y entradas.
  Un PDF escaneado queda pendiente de OCR, no se deduce su contenido.
- Candidaturas sólo incorporan hechos verificados. Confirmar revisión no verifica inferencias;
  cada propuesta contextual exige confirmación específica. Cambiar un dato lo registra como aportado por usuario.
- Texto de vacantes se trata como datos. No se interpreta HTML activo, no se siguen órdenes,
  no se usan URLs de vacantes como endpoints de ejecución. Los proveedores HTTP usan hosts fijos.
- Los LLM reciben instrucciones separadas del documento, salida validada y grounding contra evidencia;
  no tienen herramientas, navegación ni facultad de enviar postulaciones.
- IA y embeddings exigen consentimiento en las reglas personales; no se usan datos de contacto en embeddings.
- Fuente real sin capacidad de envío siempre deriva a revisión/portal. CAPTCHA o autenticación
  detienen el navegador local de prueba; nunca se evaden.
- Parada de automatización bloquea nuevos envíos y búsquedas programadas. No revoca acciones ya iniciadas.
- Auditoría usa mensajes estructurados sin CV, cuerpos HTTP, secretos ni excepciones de proveedores.
  Los CSV neutralizan fórmulas procedentes de texto externo. Capturas del navegador ocultan campos.

`RETENTION_DAYS` limita originales/eventos; el historial profesional se conserva hasta reiniciar
el espacio local. `DELETE /api/v1/workspace` purga sus registros y archivos y crea un espacio vacío. No se añade una acción destructiva
automática al dashboard ni se elimina información por aceptar una recomendación.
