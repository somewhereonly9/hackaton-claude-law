# Editor de documentos legales asistido por IA — Diseño

- **Fecha:** 2026-10-31
- **Estado:** aprobado
- **Tipo:** prueba de concepto para hackatón (prima que funcione de punta a punta, no la escala)

## 1. Objetivo

Una aplicación web donde cada usuario redacta documentos legales en un editor de texto enriquecido, con ayuda de un agente de IA que usa **el conocimiento que ese mismo usuario subió** (contratos modelo, leyes, criterios propios). Los documentos se exportan a Word y PDF.

**Criterio de éxito de la demo:** un usuario inicia sesión, sube un PDF con su conocimiento, pide al agente un documento completo, ve cómo se redacta en tiempo real, mejora un párrafo seleccionado aceptando una sugerencia y lo exporta a `.docx` y PDF. Un segundo usuario no ve nada de lo anterior.

## 2. Alcance

**Dentro:**
- Inicio y cierre de sesión. **No hay registro público:** las cuentas las crea un administrador.
- Panel de administración: crear usuarios, asignar o restablecer contraseñas, activar y desactivar cuentas.
- Documentos por usuario: crear, listar, renombrar, borrar, editar con autoguardado.
- Exportación a `.docx` y PDF.
- Subida de conocimiento por usuario (PDF, DOCX, TXT) e indexación RAG aislada por usuario.
- Agente con prioridades, en este orden:
  - **A.** Redactar un documento completo a partir de una instrucción.
  - **B.** Ayudar sobre el texto seleccionado: reescribir, insertar cláusula, revisar riesgos.
  - **C.** Chat lateral sobre los documentos y el conocimiento del usuario, que puede proponer ediciones. Se hace al final.

**Fuera:**
- Importar o editar `.docx` existentes con fidelidad de Word.
- Edición colaborativa simultánea (sin WebSockets).
- OCR de PDF escaneados.
- Roles, equipos o compartir documentos entre usuarios.
- Pruebas end-to-end de navegador, CI y pruebas de carga.

## 3. Decisiones

| Tema | Decisión | Alternativas descartadas |
|---|---|---|
| Backend | Python 3.12 + FastAPI | — |
| Front | Jinja2 + HTMX renderizado en servidor; TipTap para el editor, cargado como módulos ES desde CDN, sin build | PHP (dos runtimes y lógica duplicada); SPA con React (innecesaria) |
| Motor del agente | Ciclo propio en Python dentro de FastAPI | OpenCode (pensado para código, herramientas de terminal riesgosas en multiusuario, otro proceso); PydanticAI (dependencia extra) |
| Inferencia | API de kilopass mediante el SDK `openai` con `base_url` propio | — |
| Embeddings | kilopass si los ofrece; si no, la función local por defecto de Chroma | — |
| Vector store | Chroma persistente en disco, una colección por usuario | — |
| Base de datos | MySQL 8 en el mismo droplet; SQLAlchemy 2 + PyMySQL; migraciones con Alembic | Clúster administrado aparte (descartado por rapidez) |
| Exportación | TipTap JSON → `.docx` con `python-docx`; `.docx` → PDF con LibreOffice headless | — |
| Despliegue | Un droplet: Nginx → uvicorn (systemd), MySQL, LibreOffice, Chroma en disco | — |

**Supuesto por verificar:** kilopass expone una API compatible con OpenAI y soporta *tool calling* (el usuario ya lo usó así). La **primera tarea del plan** lo confirma con un script de humo, y también si ofrece embeddings.

## 4. Arquitectura

```
Navegador ── TipTap (editor) + HTMX ──┐
                                      ▼
Droplet:  Nginx → uvicorn (FastAPI)
             ├─ web/          páginas Jinja2 (login, lista de documentos, editor, conocimiento)
             ├─ auth/         login, sesión por cookie firmada, hash de contraseñas
             ├─ admin/        panel de administración de usuarios (solo administradores)
             ├─ documentos/   CRUD; contenido TipTap (JSON) en MySQL
             ├─ exportar/     TipTap JSON → .docx → PDF
             ├─ conocimiento/ subir → extraer texto → fragmentar → embeddings → Chroma
             ├─ agente/       ciclo con herramientas; streaming SSE
             └─ llm/          cliente único hacia kilopass (chat y embeddings)
                     │                    │
              MySQL (local)        Chroma (disco)     Archivos originales (disco)
```

**Reglas de frontera:**
- Solo `llm/` habla con kilopass. Cambiar de proveedor toca un solo módulo.
- Solo `conocimiento/` habla con Chroma. `agente/` lo usa a través de una función `buscar(usuario_id, consulta, k)`.
- Las rutas obtienen `usuario_id` exclusivamente de la sesión. **Ninguna herramienta del agente recibe `usuario_id` del modelo**: el ciclo del agente lo inyecta desde la sesión.

## 5. Modelo de datos (MySQL)

- **usuarios:** `id`, `email` (único), `nombre`, `password_hash` (Argon2), `es_admin` (bool), `activo` (bool), `creado_en`.
- **documentos:** `id`, `usuario_id` (FK), `titulo`, `contenido` (JSON de TipTap), `creado_en`, `actualizado_en`.
- **archivos_conocimiento:** `id`, `usuario_id` (FK), `nombre_original`, `ruta_disco`, `tipo` (pdf/docx/txt), `tamano_bytes`, `estado` (procesando/listo/error), `mensaje_error`, `num_fragmentos`, `creado_en`.
- **documento_fuentes:** `id`, `documento_id` (FK), `archivo_id` (FK), `fragmento_id`, `creado_en`. Registra qué fragmentos usó el agente al redactar.

**Chroma:**
- Colección `usuario_<id>`.
- Cada fragmento tiene id `a<archivo_id>-f<n>` y metadatos `archivo_id`, `posicion` y `nombre_archivo`.
- Al borrar un archivo se borran sus fragmentos.

**Disco:**
- Los archivos originales van en `data/archivos/<usuario_id>/<uuid>.<ext>`. Nunca se usa el nombre original como ruta.

## 6. Flujos

### Subir conocimiento
1. El usuario sube un archivo. Se valida:
   - tamaño de 20 MB como máximo;
   - tipo real por contenido (firma del archivo), no solo por la extensión.
2. Se guarda en disco y se registra con estado `procesando`.
3. En segundo plano (`BackgroundTasks` de FastAPI, en el mismo proceso):
   - se extrae el texto (`pypdf`, `python-docx` o lectura directa);
   - se fragmenta en trozos de unos 1,000 caracteres con 150 de traslape, respetando párrafos;
   - se generan los embeddings y se guarda en la colección del usuario;
   - el estado pasa a `listo` con el número de fragmentos.
4. Cualquier fallo deja el estado en `error` con su motivo. Ejemplo: un PDF sin texto extraíble da "el PDF no contiene texto (¿escaneado?)".
5. **Al arrancar la app,** los registros que quedaron en `procesando` pasan a `error` ("procesamiento interrumpido"). Así se cubre un reinicio a mitad del proceso.

### A. Redactar un documento completo
1. En el editor, el usuario escribe una instrucción.
2. `POST` crea una ejecución del agente. El navegador abre un `EventSource` (SSE) hacia ella.
3. El agente llama a `buscar_conocimiento` las veces que necesite y redacta en un subconjunto de HTML: `h1`–`h3`, `p`, `ul`/`ol`/`li`, `strong`, `em`.
4. El servidor acumula los tokens y emite eventos `bloque` **solo cuando un bloque HTML está completo**, para no mandar etiquetas rotas. TipTap inserta cada bloque al final del documento.
5. Al terminar:
   - se emite `fin`;
   - se guarda el documento;
   - se registran las fuentes en `documento_fuentes`;
   - la interfaz muestra los archivos consultados.

### B. Ayudar sobre lo seleccionado
1. El usuario selecciona texto y elige una acción: **reescribir**, **insertar cláusula** o **revisar riesgos**.
2. El navegador envía:
   - el texto seleccionado;
   - unos 2,000 caracteres de contexto antes y después;
   - la acción;
   - una instrucción opcional.
3. El agente consulta el conocimiento y responde con la herramienta `proponer_cambios`. **Revisar riesgos** responde además con observaciones en texto.
4. El editor resalta el rango original y muestra la propuesta en un panel flotante junto a él, con **Aceptar** y **Rechazar**. Al aceptar, se reemplaza el rango o se inserta después de él. Nada cambia sin la confirmación del usuario.

### C. Chat lateral (al final)
- Es un panel con historial por documento. Usa las mismas herramientas.
- Las ediciones que proponga pasan por el mismo mecanismo de aceptar o rechazar que en B.

## 7. Agente

- **Ciclo:**
  1. Se envían al modelo los mensajes y las herramientas.
  2. Si pide herramientas, se ejecutan y se devuelven los resultados.
  3. Se repite hasta obtener una respuesta final, con un **máximo de 8 iteraciones de herramientas**.
  4. Al llegar al límite, se pide al modelo una respuesta final sin herramientas.
- **Herramientas:**
  - `buscar_conocimiento(consulta: str, k: int = 5)`: devuelve fragmentos con `archivo_id`, `nombre_archivo` y el texto. Siempre busca en la colección del usuario de la sesión.
  - `leer_documento()`: devuelve el texto del documento abierto, o de la selección y su contexto en el flujo B.
  - `proponer_cambios(tipo: "reemplazar" | "insertar_despues", html: str, explicacion: str)`: no modifica nada en el servidor; su resultado viaja al navegador como evento SSE `propuesta`.
- **Eventos SSE:** `estado` (por ejemplo, "consultando conocimiento…"), `bloque`, `propuesta`, `texto` (chat y riesgos), `fuentes`, `error` y `fin`.
- **Prompt de sistema:**
  - Asistente de redacción jurídica en español de México.
  - Usa el conocimiento del usuario cuando sea pertinente.
  - No inventa artículos ni leyes que no estén en el conocimiento o que no conozca con certeza.
  - Responde en el subconjunto de HTML permitido.
- **El HTML generado** se sanea en el servidor con una lista blanca de etiquetas antes de enviarlo al navegador.

## 8. Interactividad

- **AJAX con HTMX y `fetch`:** acciones normales, como crear, renombrar, borrar o subir.
- **Autoguardado del editor:** `PUT` con el JSON de TipTap unos 2 segundos después del último cambio (*debounce*), más un indicador de "guardado".
- **SSE:** respuestas del agente en tiempo real.
- **Polling HTMX cada 2–3 s:** solo para el estado de los archivos en `procesando`. Se detiene al llegar a `listo` o `error`.
- **Sin WebSockets.**

## 9. Seguridad y aislamiento

- **Sesión:** cookie firmada con `SECRET_KEY`, `HttpOnly` y `SameSite=Lax`. En producción, además, `Secure` detrás de HTTPS.
- **Contraseñas:** se guardan como hash Argon2 (con sal), nunca en texto plano ni cifradas de forma reversible. Nadie puede leerlas, ni el administrador: solo puede asignar una nueva.
- **Administración:**
  - las rutas de `admin/` exigen `es_admin`; cualquier otro usuario recibe `404`;
  - el administrador gestiona cuentas, pero **no ve los documentos ni el conocimiento de los usuarios**;
  - un usuario con `activo = false` no puede iniciar sesión y sus sesiones abiertas dejan de valer;
  - un administrador no puede desactivarse ni quitarse el rol a sí mismo, para no quedarse sin acceso;
  - el primer administrador se crea desde la terminal del servidor: `python -m app.cli crear-admin`.
- **Aislamiento en MySQL:** toda consulta de documentos, archivos o fuentes filtra por `usuario_id` de la sesión. Si un recurso pertenece a otro usuario, la respuesta es `404`, no `403`, para no revelar que existe.
- **Aislamiento en Chroma:** una colección por usuario; el nombre de la colección se calcula solo en `conocimiento/` a partir del `usuario_id`.
- **Archivos:** límite de tamaño, validación de tipo por contenido y nombres en disco generados con UUID.
- **Secretos:** solo en `.env`, que git ignora. `.env.example` documenta las variables.

## 10. Manejo de errores

- **kilopass:**
  - tiempo límite por llamada y un reintento ante errores de red o 5xx;
  - si falla a mitad del streaming, se emite `error`, el editor conserva los bloques ya insertados y ofrece **Reintentar**.
- **Agente:** el límite de iteraciones evita bucles. Si una herramienta lanza una excepción, el error se devuelve al modelo como resultado de la herramienta, no se cae la ejecución.
- **Ingesta:** el fallo de un archivo no afecta a los demás; el motivo se muestra en la lista.
- **Exportación:** si LibreOffice falla, el `.docx` sigue disponible y se informa que el PDF no se pudo generar.

## 11. Pruebas (pytest)

- **Administración:** un usuario normal recibe `404` en las rutas de admin; un usuario desactivado no puede iniciar sesión; el administrador no puede desactivarse a sí mismo.
- **Aislamiento entre usuarios, que es la prueba prioritaria:**
  - B no puede ver, editar, exportar ni borrar documentos ni archivos de A;
  - `buscar_conocimiento` en la sesión de B nunca devuelve fragmentos de A.
- **Agente con un LLM falso** (sin llamadas reales): ejecuta herramientas, inyecta el usuario de la sesión, respeta el máximo de iteraciones y convierte las excepciones en resultados de herramienta.
- **Emisión de bloques:** el acumulador solo emite bloques HTML completos y saneados.
- **Ingesta:** extracción y fragmentación de PDF, DOCX y TXT pequeños de ejemplo; un PDF sin texto termina en `error`.
- **Exportación:** de un JSON de TipTap de ejemplo salen un `.docx` válido y, si LibreOffice está instalado, un PDF.
- **Base de datos de pruebas:** se corren contra una base MySQL separada (`MYSQL_DATABASE` de prueba).
- **Humo de kilopass:** un script manual (`scripts/probar_kilopass.py`) que verifica chat, *tool calling* y embeddings con la clave real.

## 12. Orden de construcción

Cada pieza deja la app funcionando. Cada tarea termina en commit y push.

1. **Verificación de kilopass:** el script de humo. Su resultado decide de dónde salen los embeddings.
2. **Base:**
   - esqueleto de FastAPI, configuración y MySQL con Alembic;
   - autenticación, comando `crear-admin` y panel de administración de usuarios;
   - CRUD de documentos;
   - editor TipTap con autoguardado;
   - exportación a `.docx` y PDF.
3. **Conocimiento:** subida, ingesta en segundo plano, Chroma por usuario y lista con estados.
4. **Agente A:** cliente `llm/`, ciclo, herramientas, SSE y redacción completa con fuentes.
5. **Agente B:** acciones sobre la selección y propuestas que se aceptan o rechazan.
6. **Agente C:** chat lateral.
7. **Despliegue en el droplet:** Nginx, systemd, MySQL y LibreOffice. Se actualiza `CLAUDE.md` con los comandos reales.

## 13. Riesgos

- **Embeddings locales en español:** la función por defecto de Chroma (`all-MiniLM-L6-v2`) está orientada al inglés. Si kilopass no ofrece embeddings y la calidad de búsqueda es mala, se cambia a un modelo multilingüe (`paraphrase-multilingual-MiniLM-L12-v2` vía `sentence-transformers`), que pesa más en el droplet.
- **Memoria del droplet:** el droplet actual es Ubuntu 24.04, 1 vCPU, **1 GB de RAM** y 35 GB de disco (DigitalOcean, SFO3). Es justo para MySQL, la app, Chroma y LibreOffice. Mitigaciones obligatorias:
  - archivo de swap de 2 GB;
  - MySQL afinado para poca memoria (`innodb_buffer_pool_size=128M`, `performance_schema=OFF`);
  - un solo worker de uvicorn y una sola conversión de LibreOffice a la vez;
  - preferir embeddings de kilopass; si no hay, solo el modelo ONNX por defecto de Chroma, nunca `sentence-transformers` con torch.

  Si la demo va lenta, se escala el droplet a 2 GB.
- **Python 3.12 (confirmado):** se fija esta versión porque algunas dependencias (Chroma) pueden no tener todavía ruedas para versiones más nuevas. En el droplet y en local se usa un entorno virtual con 3.12.
