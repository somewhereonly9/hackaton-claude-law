# Estado del proyecto y cómo retomarlo

**Última actualización:** 2026-10-31, al cerrar el Plan 1.

Este archivo sirve para que cualquier sesión nueva de Claude Code, u otra persona, retome el trabajo donde quedó. La arquitectura, los comandos y las convenciones están en `CLAUDE.md`.

## Plan 1 (base): terminado

| Task | Commits |
|---|---|
| 1. Esqueleto, configuración y MySQL | `7e5f245` |
| 2. Prueba de humo de kilopass | `23ed7c5` |
| 3. Modelos, migración y contraseñas | `abb7ce5`, `86fb937` |
| 4. Login, sesiones y `crear-admin` | `0d53b67`, `a2df516` |
| 5. Panel de administración | `1f4b2bc` |
| 6. Documentos por usuario | `56b772c` |
| 7. Editor TipTap + autoguardado | `eac6209`, `08aefd7` |
| 8. Exportación a .docx | `38ae84d`, `b9e3790` |
| 9. Exportación a PDF y descargas | `9d2fb98`, `b5d4f98` |
| Despliegue por IP (fuera del plan, pedido por el usuario) | `06cbb66` |
| Correcciones de la revisión final | `81de7f9`, `1ffecb1` |

**Cómo se revisó:**
- cada tarea la implementó Sonnet y la revisó Fable, con rondas de corrección cuando hizo falta;
- al final, Fable revisó todo el plan y sus hallazgos se corrigieron en una sola ronda, también revisada.

**Estado de las pruebas:** 65 en verde. `test_pdf_real` se omite en la Mac; el PDF real se verificó en el droplet.

## En producción

- **Dirección:** http://64.23.245.92, solo por IP.
- **Cómo actualizar:** ver la sección "Despliegue" de `CLAUDE.md`.
- **Pendiente:**
  - el dominio, que pasará el usuario;
  - HTTPS con Let's Encrypt;
  - `COOKIE_SEGURA=true` en el `.env` del servidor;
  - la `KILOPASS_API_KEY` del servidor, que pone el usuario.

## Siguientes pasos

1. **Plan 2 (conocimiento / RAG).** Se escribe con las ideas guardadas en engram (proyecto `hackatonclaudelaw`, tema `plan2/ideas-rag`):
   - fragmentación por estructura legal;
   - ids deterministas con `upsert` y hash del archivo;
   - ingesta de un archivo y por lotes;
   - embeddings locales ONNX;
   - umbral calibrado con un mini conjunto de preguntas.
2. **Plan 3 (agente A):**
   - el cliente `llm/` debe nacer con `timeout` y `max_retries`;
   - el agente guarda siempre a través de `documentos.servicio.guardar_contenido`;
   - agregar la herramienta `buscar_jurisprudencia` con la API `https://corpusiuris.mx/conecta`. Antes hay que preguntar al usuario si es REST o MCP, cómo se autentica y pedirle un ejemplo de respuesta.
3. **Plan 5 (despliegue):**
   - HTTPS y cookie `Secure`;
   - `acquire(timeout)` en el cerrojo del PDF, para que una cola de descargas no agote los hilos ni el pool de la BD;
   - `limit_req` en `/login`;
   - cabeceras de seguridad;
   - `proxy_buffering off` para el SSE del agente.

## Hallazgos menores diferidos (no bloquean)

- `/documentos/abc` responde 422 en lugar de 404.
- Si falla el borrado con HTMX, no se avisa al usuario. Además, al borrar la última fila la tabla queda vacía.
- Las fechas se muestran en UTC, sin convertir a la zona del usuario.
- Las listas anidadas se exportan al `.docx` sin sangría. Hay que tenerlo en cuenta si el agente redacta incisos anidados.
- Las clases CSS `tabla` y `formulario` no tienen estilos.
- El `<title>` de la pestaña no se actualiza al renombrar el documento.
