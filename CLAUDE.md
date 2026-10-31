# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Editor web de documentos legales asistido por IA, hecho para un hackatón. Los jueces revisan el historial de git y estas instrucciones.

- **Plan 1 (base): terminado y desplegado.** Incluye login, panel de administración, documentos por usuario, editor TipTap con autoguardado y exportación a `.docx` y PDF.
- **Pendientes:**
  - Plan 2: conocimiento por usuario (RAG con Chroma y embeddings locales ONNX).
  - Plan 3: agente A, que redacta un documento completo con fuentes.
  - Plan 4: agentes B y C, que trabajan sobre la selección y en un chat lateral.
  - Plan 5: endurecimiento del despliegue y HTTPS.
- **Documentos de referencia:**
  - spec: `docs/superpowers/specs/2026-10-31-editor-documentos-legales-design.md`;
  - plan: `docs/superpowers/plans/2026-10-31-plan-1-base.md`;
  - estado y cómo retomar: `docs/superpowers/ESTADO.md`.

## Stack

- **Lenguaje:** Python 3.12 exacto, gestionado con `uv` (`uv.lock` está versionado).
- **Web:** FastAPI con Jinja2 y HTMX 2, renderizado en servidor.
- **Editor:** TipTap 2.27.3, cargado como módulos ES desde esm.sh, sin build.
- **Datos:** MySQL 8 con SQLAlchemy 2, PyMySQL y Alembic.
- **Contraseñas:** hash Argon2 (`argon2-cffi`).
- **Exportación:** `python-docx` para `.docx` y LibreOffice headless para PDF.
- **LLM:** kilopass (Kilo Gateway), API compatible con OpenAI y tool calling verificado. No ofrece modelos de embeddings, así que el Plan 2 usará embeddings locales.

## Comandos

```bash
uv sync                                          # crea .venv (Python 3.12) e instala dependencias
uv run uvicorn app.main:app --reload             # servidor de desarrollo
uv run pytest -q                                 # todas las pruebas
uv run pytest tests/archivo.py::nombre -v        # una sola prueba
uv run alembic upgrade head                      # aplica las migraciones
uv run python -m app.cli crear-admin             # crea un administrador (interactivo)
uv run python scripts/probar_kilopass.py         # prueba de humo de kilopass (chat + tool calling)
```

**Pruebas:**
- requieren MySQL local y `MYSQL_TEST_DATABASE`, una base distinta de `MYSQL_DATABASE` que se vacía en cada prueba;
- los helpers son `crear` y `entrar`, en `tests/helpers.py`;
- `test_pdf_real` se omite si no hay LibreOffice (en la Mac no está; en el droplet sí).

La configuración se lee de `.env` (ver `.env.example`).

## Arquitectura

```
app/
  main.py         crea la app: sesión, estáticos, routers y manejadores de NoAutenticado / NoEncontrado
  config.py       Settings (pydantic-settings) leídos de .env
  db.py           dependencia de sesión de BD
  modelos.py      Usuario, Documento
  cli.py          crear-admin
  auth/           login, logout, sesión firmada, hash Argon2, dependencias usuario_actual / admin_actual
  usuarios/       servicio de usuarios (crear, listar, contraseña, activar)
  admin/          panel de administración (/admin/usuarios)
  documentos/     servicio y rutas de documentos; GET /documentos/{id} es el editor
  exportar/       word.py (TipTap JSON → .docx), pdf.py (.docx → PDF), rutas de descarga
  web/            render.py (templates), plantillas/, estaticos/ (estilos.css, editor.js)
migraciones/      Alembic
deploy/           servicio systemd, sitio Nginx, actualizar.sh
```

**Flujo de una petición:**
1. La dependencia `usuario_actual` lee la cookie de sesión firmada. Si el usuario no existe o está inactivo, lanza `NoAutenticado`.
2. El servicio filtra siempre por `usuario_id` y hace `commit` al escribir.
3. Los datos se guardan en MySQL.

**Errores:** son JSON para `fetch` y HTMX. En la navegación normal del navegador, un 404 muestra una página HTML y la falta de sesión redirige a `/login`.

**Documento:** el contenido es el JSON de TipTap con raíz `{"type": "doc", ...}`, con un máximo de 2 MB. `editor.js` hace el autoguardado con un `PUT /documentos/{id}/contenido` 2 s después del último cambio, con un solo PUT en vuelo a la vez. La instancia del editor queda en `window.editorDocumento` para los planes del agente.

**Exportación:**
- `tiptap_a_docx` nunca lanza excepciones y reinicia la numeración en cada lista ordenada.
- `docx_a_pdf` permite una sola conversión a la vez (cerrojo por proceso), con un tiempo límite de 60 s y perfil persistente en `data/lo_perfil`. Si se agota el tiempo, mata todo el grupo de procesos.
- Si el PDF falla, la ruta responde 503 y el `.docx` sigue disponible.

## Convenciones (obligatorias)

- **Aislamiento:**
  - un recurso ajeno o inexistente responde 404, nunca 403;
  - las rutas de admin responden 404 a quien no es admin.
- **Plantillas:**
  - se importan con `from app.web.render import templates`;
  - se renderizan con `templates.TemplateResponse(request, "x.html", ctx)`, siempre con `usuario` en `ctx`;
  - los enlaces hacia rutas de tareas futuras son hrefs literales, nunca `url_for`.
- **Servicios y rutas de archivos:**
  - toda función de servicio que escribe hace `db.commit()`;
  - las rutas de archivos se calculan desde `Path(__file__)`, nunca desde el directorio de trabajo.
- **Idioma:** código de dominio, textos de interfaz y commits en español.
- **Producto de referencia:** el producto comercial que inspira el proyecto se llama "work". Su nombre real nunca aparece en código, comentarios, commits ni archivos.
- **Secretos:**
  - viven solo en `.env`;
  - nunca se lee, se imprime ni se hace `source` de `.env`;
  - toda variable nueva se agrega vacía a `.env.example`.
- **Commits:**
  - un commit y un push a `main` por paso;
  - los archivos se agregan por nombre, nunca con `git add -A`;
  - cada mensaje termina con el trailer `Co-Authored-By: Claude <modelo> <noreply@anthropic.com>`.
- **Código propio:** todo se escribe desde cero en este repo, sin copiar código de otros proyectos.

## Despliegue

- **Servidor:** droplet de DigitalOcean (1 vCPU, 1 GB de RAM, 2 GB de swap), acceso con `ssh hackaton`. La app está en https://editorwork.dagdugrangel.com.mx (registro A en el DNS de GoDaddy de dagdugrangel.com.mx → 64.23.245.92). Si se entra por la IP o por http, Nginx redirige al dominio con HTTPS.
- **Instalación:**
  - el código vive en `/srv/editor/app`, con el usuario de sistema `editor`;
  - el servicio systemd es `editor` (`deploy/editor.service`), con uvicorn y `--workers 1`, que el cerrojo del PDF exige;
  - Nginx usa `deploy/nginx-editor.conf`.
- **Actualizar:** `ssh hackaton 'bash /srv/editor/app/deploy/actualizar.sh'` (hace pull, `uv sync`, migraciones y reinicio).
- **`.env` del servidor:** se generó allí y nunca se imprime.
- **HTTPS:** certificado de Let's Encrypt con renovación automática (`certbot.timer`). `deploy/nginx-editor.conf` es la configuración completa instalada, con las líneas que agregó `certbot --nginx`. El `.env` del servidor tiene `COOKIE_SEGURA=true`.
