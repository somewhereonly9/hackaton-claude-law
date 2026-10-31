# Estado del proyecto y cómo retomarlo

**Última actualización:** 2026-10-31, al terminar la implementación de la Task 5 del Plan 1.

Este archivo sirve para que cualquier sesión nueva de Claude Code (u otra persona) retome el trabajo exactamente donde quedó.

## Qué estamos construyendo

Un editor web de documentos legales asistido por IA:
- Python 3.12 + FastAPI, con Jinja2 + HTMX y el editor TipTap.
- MySQL.
- RAG por usuario con Chroma.
- Un agente con herramientas que usa el Kilo Gateway.

| Documento | Ruta |
|---|---|
| Especificación (aprobada) | `docs/superpowers/specs/2026-10-31-editor-documentos-legales-design.md` |
| Plan 1, en ejecución | `docs/superpowers/plans/2026-10-31-plan-1-base.md` |
| Comandos | `CLAUDE.md` |

## Reglas del proyecto (no negociables)

1. **Commit y push a `main` al terminar cada paso.** Los jueces del hackatón revisan el historial de git y las instrucciones.
2. **Todo se construye desde cero en este repo.** No se copia código de otros proyectos de la máquina. Tomar ideas sí está permitido.
3. **El producto comercial de referencia** se llama "work" en la conversación. Su nombre real nunca aparece en código, commits ni archivos.
4. **Método de trabajo:**
   - skill `superpowers:subagent-driven-development`;
   - implementadores con **Sonnet 5.5** (`model: sonnet`);
   - revisores y re-revisores con **Fable** (`model: fable`), incluida la revisión final del plan;
   - tareas **estrictamente secuenciales**: la siguiente empieza solo cuando Fable aprueba la anterior.
5. **Secretos:** nunca leer, imprimir ni hacer `source` de `.env`. Para comprobarlo, usar scripts que solo digan "lleno" o "vacío".

## Avance del Plan 1

| Task | Estado | Commits |
|---|---|---|
| 1. Esqueleto, configuración y MySQL | ✅ aprobada | `7e5f245` |
| 2. Prueba de humo de kilopass | ✅ aprobada | `23ed7c5` |
| 3. Modelos, migración y contraseñas | ✅ aprobada (1 ronda de corrección) | `abb7ce5`, `86fb937` |
| 4. Login, sesiones y `crear-admin` | ✅ aprobada (1 ronda de corrección) | `0d53b67`, `a2df516` |
| 5. Panel de administración | **implementada, falta la revisión de Fable** | `1f4b2bc` |
| 6. Documentos por usuario | pendiente | — |
| 7. Editor TipTap + autoguardado | pendiente | — |
| 8. Exportación a .docx | pendiente | — |
| 9. Exportación a PDF y descargas | pendiente | — |

Suite actual: 28 pruebas en verde.

## Cómo retomar (paso a paso)

1. Abrir Claude Code en `/Users/dev/Workspace/hackatonclaudelaw`.
2. Pedir: *"Lee docs/superpowers/ESTADO.md y continúa la ejecución del Plan 1 con subagent-driven-development, empezando por la revisión de la Task 5."*
3. **El ledger** (registro de avance, ignorado por git) está en `.superpowers/sdd/2026-10-31-plan-1-base/progress.md`. Las tareas con la línea `Task N: complete` ya están hechas y **no se vuelven a ejecutar**. La Task 5 tiene `implementer DONE … REVIEW PENDIENTE`.
4. En la misma carpeta están:
   - `task-N-brief.md`: los requisitos de cada tarea;
   - `task-N-report.md`: los informes de los implementadores;
   - `global-constraints.md` y `estructura.md`: las reglas comunes que se pasan a los subagentes;
   - `review-a2df516..1f4b2bc.diff`: **el paquete de revisión de la Task 5, ya generado**.
5. **Siguiente acción concreta:** despachar a Fable la revisión de la Task 5 con `task-5-brief.md`, `task-5-report.md`, `global-constraints.md` y ese paquete.
   - Si pide correcciones, se reanuda al implementador o se lanza uno nuevo con el informe.
   - Si la aprueba, se escribe `Task 5: complete` en el ledger y se sigue con la Task 6.
6. Al terminar la Task 9: revisión final de todo el plan con Fable, corregir lo que salga y actualizar `CLAUDE.md`.

### Datos que las tareas siguientes deben conocer

- **Plantillas:**
  - se importan con `from app.web.render import templates`;
  - se renderizan con `templates.TemplateResponse(request, "x.html", {...})`, siempre con `usuario` en el contexto;
  - el antiguo `app/web/plantillas.py` ya no existe.
- **Helpers de pruebas:** `from tests.helpers import crear, entrar`.
- **Servicios:** cada servicio que escribe hace `commit`. Las pruebas usan la base `editor_test`.

## Entorno

- **Mac:**
  - MySQL local con usuario `root`; bases `editor` (desarrollo) y `editor_test` (pruebas);
  - `.env` lleno: MySQL, `SECRET_KEY`, `KILOPASS_API_KEY`, `KILOPASS_BASE_URL=https://api.kilo.ai/api/gateway` y `KILOPASS_MODEL=anthropic/claude-sonnet-5.5`;
  - LibreOffice no está instalado: `test_pdf_real` se omite.
- **kilopass (Kilo Gateway):**
  - chat y tool calling verificados;
  - **no ofrece modelos de embeddings**, así que el RAG usará embeddings locales ONNX (sin PyTorch).
- **Droplet** (DigitalOcean SFO3, Ubuntu 24.04, 1 vCPU, 1 GB de RAM; acceso con `ssh hackaton`):
  - swap de 2 GB;
  - MySQL 8.0.46 afinado, con la base y el usuario `editor`;
  - Nginx, LibreOffice headless, ufw y uv ya instalados;
  - el despliegue de la app va en el Plan 5.

## Pendientes fuera del Plan 1

- **Plan 2 (conocimiento / RAG):** escribirlo con las ideas guardadas en engram (proyecto `hackatonclaudelaw`, tema `plan2/ideas-rag`):
  - fragmentación por estructura legal;
  - ids deterministas con `upsert` y hash del archivo;
  - ingesta de una en una y por lotes;
  - embeddings ONNX;
  - umbral calibrado con un mini conjunto de preguntas.
- **Plan 3 (agente):** agregar la herramienta `buscar_jurisprudencia` con la API `https://corpusiuris.mx/conecta`. Antes hay que preguntar al usuario si es REST o MCP, cómo se autentica y pedirle un ejemplo de respuesta. Requiere actualizar la sección 7 de la spec.
- **Plan 4** (agente B/C) y **Plan 5** (despliegue).
- **Hallazgos menores diferidos** para la revisión final: están en el ledger, en las líneas `minor (deferred)`.
