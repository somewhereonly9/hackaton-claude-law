# Plan 2 — Conocimiento por usuario (RAG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que cada usuario suba PDF, DOCX o TXT con su conocimiento, se procese en segundo plano y se pueda buscar en él, siempre aislado por usuario. Esta búsqueda es la base del agente del Plan 3.

**Architecture:** el módulo nuevo `app/conocimiento/` sigue esta cadena:
1. valida el archivo por tamaño y por firma de bytes, lo guarda en disco y lo registra en MySQL con estado `procesando`;
2. una tarea en segundo plano extrae el texto, lo fragmenta por estructura legal, calcula embeddings locales ONNX y hace `upsert` en la colección de Chroma de ese usuario;
3. `buscar(usuario_id, consulta, k)` devuelve fragmentos con referencia ("Artículo 5", "página 3") y puntuación.

Los embeddings son un objeto inyectado en `app.state`, para que las pruebas usen uno falso, determinista y sin red.

**Tech Stack:** chromadb 1.x (`PersistentClient`), fastembed con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (ONNX, 384 dimensiones, sin PyTorch), pypdf y python-docx. Lo demás ya existe: FastAPI, Jinja2 + HTMX, SQLAlchemy y Alembic.

**Spec:** `docs/superpowers/specs/2026-10-31-editor-documentos-legales-design.md`, secciones 4, 5, 6 ("Subir conocimiento"), 8, 9, 10, 11 y 13. Las convenciones del Plan 1 están en `CLAUDE.md`.

**Fuera de este plan:**
- la tabla `documento_fuentes` y la herramienta `buscar_conocimiento` del agente, que van en el Plan 3 y usarán `servicio.buscar`;
- la búsqueda por palabra clave combinada con RRF.

## Global Constraints

- **Python:** 3.12 exacto. Las dependencias nuevas se agregan con `uv add` y `uv.lock` se versiona.
- **Embeddings:** sin `sentence-transformers` ni `torch`. Solo ONNX vía fastembed, con `threads=1`, cargado una sola vez por proceso y de forma perezosa.
- **Chroma:**
  - un solo `PersistentClient` por proceso, con `anonymized_telemetry=False`;
  - la colección de cada usuario se llama `usuario_<id>`, usa distancia coseno y su nombre se calcula **solo** en `app/conocimiento/`, a partir del `usuario_id` de la sesión.
- **Ids de fragmento:** `a<archivo_id>-f<n>`, con `n` desde 0. Se guardan con `upsert`.
- **Metadatos de cada fragmento** (ninguno puede valer `None`):
  - `archivo_id` (int);
  - `usuario_id` (int);
  - `posicion` (int);
  - `nombre_archivo` (str);
  - `pagina` (int; 0 si no aplica);
  - `articulo` (str; `""` si no hay).
- **Archivos en disco:** `data/archivos/<usuario_id>/<uuid4 hex>.<pdf|docx|txt>`, con rutas relativas a la raíz del repo calculada desde `Path(__file__)`. Nunca se usa el nombre original como ruta. Lo mismo vale para `CHROMA_PATH` y la caché de modelos (`data/modelos`) cuando sean relativas.
- **Límite de tamaño:** 20 MB (`20_971_520` bytes), comprobado antes de leer el archivo completo.
- **Tipos permitidos**, detectados por contenido y no por extensión:
  - PDF empieza con `%PDF-`;
  - DOCX es un zip (`PK\x03\x04`) que contiene `word/document.xml`;
  - TXT no tiene bytes `\x00` y se decodifica como UTF-8 o, si falla, como cp1252.
- **Fragmentación:** trozos de unos 1,000 caracteres con 150 de traslape. Respetan párrafos y encabezados legales y nunca cortan una palabra.
- **Estados:** `procesando`, `listo` y `error`. Mensajes exactos:
  - `"el PDF no contiene texto (¿escaneado?)"`;
  - `"el archivo no contiene texto"`;
  - `"procesamiento interrumpido"`.
- **Mensajes al subir**, con respuesta 400 salvo el duplicado, que es 409:
  - `"El archivo supera 20 MB."`;
  - `"Tipo de archivo no permitido: sube un PDF, DOCX o TXT."`;
  - `"Ya subiste este archivo."`.
- **Ingesta:** una a la vez, con un `threading.Lock` por proceso (exige `--workers 1`, igual que el PDF). Embeddings por lotes de 32. El fallo de un archivo no afecta a los demás.
- **Aislamiento:** toda consulta de archivos filtra por el `usuario_id` de la sesión; un recurso ajeno o inexistente responde 404. `buscar` solo devuelve fragmentos de archivos en estado `listo` del mismo usuario.
- **Convenciones del Plan 1:**
  - plantillas con `templates.TemplateResponse(request, "x.html", {...})` y `usuario` en el contexto;
  - servicios que escriben hacen `db.commit()`;
  - código, textos y commits en español;
  - un commit y un push por tarea, con trailer `Co-Authored-By`;
  - nunca leer ni imprimir `.env`, y toda variable nueva va vacía a `.env.example`.

## Review Focus

1. **Archivo disfrazado:** un `.exe` o un `.zip` renombrado a `.pdf` o `.docx` se rechaza con 400 y el mensaje de tipo; no llega a procesarse. Prueba en la Task 2 (`detectar_tipo`) y en la Task 6 (ruta).
2. **TXT de Windows con acentos (cp1252):** el texto sale con "artículo" y "ñ" correctos, sin mojibake. Prueba en la Task 2.
3. **El mismo archivo subido dos veces:** 409 "Ya subiste este archivo." sin un segundo registro ni fragmentos duplicados. Prueba en la Task 5.
4. **Borrar un archivo mientras se procesa, o reiniciar la app a mitad:**
   - `procesar` sobre un archivo ya borrado termina sin excepción y sin dejar fragmentos;
   - al arrancar, los registros en `procesando` pasan a `error`.
   Pruebas en la Task 5.
5. **Buscar sin archivos, con la consulta vacía o mientras un archivo sigue en `procesando`:** devuelve una lista vacía o solo fragmentos de archivos `listo`, sin error. Pruebas en la Task 5.

---

### Task 1: Dependencias, configuración y modelo `ArchivoConocimiento`

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (con `uv add chromadb fastembed pypdf`), `app/config.py`, `.env.example`, `app/modelos.py`
- Create: `migraciones/versions/0002_archivos_conocimiento.py`, `app/conocimiento/__init__.py`, `app/conocimiento/rutas_disco.py`, `tests/test_conocimiento_modelo.py`

**Interfaces:**
- Produces:
  - `Settings`: `chroma_path: str = "./data/chroma"` (ya existe), `archivos_path: str = "./data/archivos"`, `modelos_path: str = "./data/modelos"`, `embeddings_modelo: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"`, `umbral_similitud: float = 0.0` (la Task 7 fija el valor calibrado).
  - `app/conocimiento/rutas_disco.py`: `RAIZ: Path` (la raíz del repo) y `resolver(ruta: str) -> Path`, que devuelve la ruta tal cual si es absoluta y `RAIZ / ruta` si es relativa.
  - Modelo `ArchivoConocimiento` (tabla `archivos_conocimiento`, utf8mb4):
    - `id`;
    - `usuario_id` (FK a `usuarios.id` con `ondelete=CASCADE`, con índice);
    - `nombre_original` String(255);
    - `ruta_disco` String(500);
    - `tipo` String(10);
    - `tamano_bytes` Integer;
    - `sha256` String(64);
    - `estado` String(20), default `"procesando"`;
    - `mensaje_error` String(500), con default y server_default `""`;
    - `num_fragmentos` Integer, default 0;
    - `creado_en` DateTime con `server_default=func.now()`;
    - `UniqueConstraint("usuario_id", "sha256", name="uq_archivo_usuario_sha256")`.
  - Migración `0002`, con `down_revision = "0001"`, que crea exactamente esa tabla, su índice y la restricción de unicidad.

- [ ] **Step 1: Escribir las pruebas que fallan** en `tests/test_conocimiento_modelo.py`:

```python
def test_resolver_relativa_y_absoluta():
    assert resolver("./data/x") == RAIZ / "data" / "x"
    assert resolver("/tmp/y") == Path("/tmp/y")

def test_archivo_se_borra_con_su_usuario(db):
    u = crear(db, "a@x.com")
    db.add(ArchivoConocimiento(usuario_id=u.id, nombre_original="a.pdf", ruta_disco="x", tipo="pdf", tamano_bytes=1, sha256="0" * 64)); db.commit()
    db.delete(u); db.commit()
    assert db.scalar(select(func.count()).select_from(ArchivoConocimiento)) == 0

def test_sha256_unico_por_usuario(db):
    u = crear(db, "a@x.com")
    for _ in range(2):
        db.add(ArchivoConocimiento(usuario_id=u.id, nombre_original="a.pdf", ruta_disco="x", tipo="pdf", tamano_bytes=1, sha256="1" * 64))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: Correr y verificar que fallan.** Run: `uv run pytest tests/test_conocimiento_modelo.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implementar** las dependencias, los settings (agrega a `.env.example`, vacías y comentadas, `ARCHIVOS_PATH`, `MODELOS_PATH`, `EMBEDDINGS_MODELO` y `UMBRAL_SIMILITUD`), `rutas_disco.py`, el modelo y la migración `0002`.
- [ ] **Step 4: Verificar.**
  - `uv run pytest -q`: todas pasan.
  - `uv run alembic upgrade head` sobre la base de desarrollo: aplica `0002` sin error.
  - `uv run alembic downgrade -1 && uv run alembic upgrade head`: ida y vuelta sin error.
- [ ] **Step 5: Commit y push.** Mensaje: "Modelo de archivos de conocimiento, migración 0002 y configuración del RAG".

### Task 2: Detección de tipo y extracción de texto

**Files:**
- Create: `app/conocimiento/extraer.py`, `tests/test_conocimiento_extraer.py`
- Modify: `tests/helpers.py` (agrega `pdf_minimo`)

**Interfaces:**
- Produces:
  - `TipoNoPermitido(Exception)` y `SinTexto(Exception)`; el mensaje de esta última es el del estado de error.
  - `detectar_tipo(cabecera: bytes, ruta: Path) -> str`: devuelve `"pdf"`, `"docx"` o `"txt"`, o lanza `TipoNoPermitido`. `cabecera` son los primeros 8 KB; `ruta` sirve para abrir el zip y comprobar `word/document.xml`.
  - `@dataclass Pagina(numero: int, texto: str)`: `numero` empieza en 1 para PDF y es 0 para DOCX y TXT.
  - `extraer(ruta: Path, tipo: str) -> list[Pagina]`:
    - limpia el texto: quita las líneas de encabezado y pie que se repiten en más de la mitad de las páginas (solo PDF con 3 páginas o más, y solo la primera y la última línea no vacía de cada página), une las palabras cortadas con guion al final de línea (`"contra-\nto"` → `"contrato"`) y normaliza los espacios;
    - lanza `SinTexto("el PDF no contiene texto (¿escaneado?)")` si un PDF no da texto, o `SinTexto("el archivo no contiene texto")` para DOCX o TXT vacíos.
  - `tests/helpers.py`: `pdf_minimo(paginas: list[str]) -> bytes`, que arma un PDF válido de una o más páginas con una fuente estándar Helvetica y texto ASCII, a mano y sin dependencias nuevas, para que pypdf pueda extraerlo. Cada `"\n"` de una página se dibuja como una línea aparte (un `Td` por línea), para que pypdf devuelva líneas separadas. Con `pdf_minimo([""])` el PDF no tiene texto.

- [ ] **Step 1: Escribir las pruebas que fallan:**

```python
def test_detecta_tipos_por_contenido(tmp_path):
    p = tmp_path / "a.bin"; p.write_bytes(pdf_minimo(["Hola"]))
    assert detectar_tipo(p.read_bytes()[:8192], p) == "pdf"
    d = tmp_path / "b.bin"; documento = docx.Document(); documento.add_paragraph("Hola"); documento.save(d)
    assert detectar_tipo(d.read_bytes()[:8192], d) == "docx"
    t = tmp_path / "c.bin"; t.write_bytes("Cláusula".encode("cp1252"))
    assert detectar_tipo(t.read_bytes()[:8192], t) == "txt"

def test_rechaza_disfrazados(tmp_path):
    z = tmp_path / "x.docx"
    with zipfile.ZipFile(z, "w") as zf: zf.writestr("otro.txt", "x")
    exe = tmp_path / "x.pdf"; exe.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00")
    for p in (z, exe):
        with pytest.raises(TipoNoPermitido):
            detectar_tipo(p.read_bytes()[:8192], p)

def test_txt_cp1252_conserva_acentos(tmp_path):
    t = tmp_path / "a.txt"; t.write_bytes("Artículo 1. La compañía".encode("cp1252"))
    assert "Artículo 1. La compañía" in extraer(t, "txt")[0].texto

def test_pdf_por_paginas_y_sin_encabezados_repetidos(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(pdf_minimo([f"DESPACHO X\nTexto de la pagina {i}\nPagina {i}" for i in (1, 2, 3)]))
    paginas = extraer(p, "pdf")
    assert [pg.numero for pg in paginas] == [1, 2, 3]
    assert "Texto de la pagina 2" in paginas[1].texto and "DESPACHO X" not in paginas[1].texto

def test_une_guiones_de_fin_de_linea(tmp_path):
    t = tmp_path / "a.txt"; t.write_text("el contra-\nto de arrendamiento", encoding="utf-8")
    assert "el contrato de arrendamiento" in extraer(t, "txt")[0].texto

def test_pdf_sin_texto(tmp_path):
    p = tmp_path / "a.pdf"; p.write_bytes(pdf_minimo([""]))
    with pytest.raises(SinTexto, match="escaneado"):
        extraer(p, "pdf")
```

- [ ] **Step 2: Correr y verificar que fallan.** Run: `uv run pytest tests/test_conocimiento_extraer.py -v`. Expected: FAIL.
- [ ] **Step 3: Implementar** `extraer.py` con `pypdf.PdfReader` y `docx.Document`, más el helper `pdf_minimo`. Para DOCX, los párrafos se unen con `"\n\n"`.
- [ ] **Step 4: Verificar.** Run: `uv run pytest tests/test_conocimiento_extraer.py -v`. Expected: PASS.
- [ ] **Step 5: Commit y push.** Mensaje: "Detección de tipo por contenido y extracción de texto de PDF, DOCX y TXT".

### Task 3: Fragmentación por estructura legal

**Files:**
- Create: `app/conocimiento/fragmentar.py`, `tests/test_conocimiento_fragmentar.py`

**Interfaces:**
- Consumes: `Pagina` (Task 2).
- Produces:
  - `TAMANO = 1000` y `TRASLAPE = 150`;
  - `@dataclass Fragmento(posicion: int, texto: str, pagina: int, articulo: str)`;
  - `fragmentar(paginas: list[Pagina]) -> list[Fragmento]`.

**Algoritmo** (el implementador no lo puede deducir de la firma):
1. Divide cada página en párrafos por líneas en blanco, conservando el número de página de cada uno.
2. Un párrafo cuyo inicio coincide con `^(ART[IÍ]CULO|Art[ií]culo|CAP[IÍ]TULO|Cap[ií]tulo|CL[AÁ]USULA|Cl[aá]usula|T[IÍ]TULO|T[ií]tulo|SECCI[OÓ]N|Secci[oó]n)\s+[\w.]+` es un **encabezado**. Actualiza el `articulo` vigente con el texto que coincidió, sin puntos ni dos puntos al final (`"Artículo 5."` → `"Artículo 5"`), y, si el trozo en curso ya tiene contenido, lo cierra, para que cada artículo empiece trozo nuevo.
3. Acumula párrafos mientras el trozo no pase de `TAMANO`. Un párrafo de más de `TAMANO` se parte por oraciones (`. `, `; `), o por espacios si una oración sola excede el tamaño.
4. Cada trozo nuevo dentro del mismo artículo empieza con los últimos ~`TRASLAPE` caracteres del anterior, recortados al primer espacio para no partir palabras.
5. `pagina` es la página del primer párrafo del trozo y `articulo` es el vigente al empezar. Las posiciones van de 0 en adelante.

- [ ] **Step 1: Escribir las pruebas que fallan:**

```python
def test_cada_articulo_empieza_fragmento():
    texto = "Artículo 1. Objeto del contrato.\n\nTexto uno.\n\nArtículo 2. Precio.\n\nTexto dos."
    fr = fragmentar([Pagina(0, texto)])
    assert [f.articulo for f in fr] == ["Artículo 1", "Artículo 2"]
    assert fr[1].texto.startswith("Artículo 2")

def test_tamano_y_traslape_sin_cortar_palabras():
    texto = " ".join(f"palabra{i}" for i in range(600))
    fr = fragmentar([Pagina(1, texto)])
    assert len(fr) > 1 and all(len(f.texto) <= TAMANO + 50 for f in fr)
    assert all(not f.texto[0].isspace() and f.texto.split()[0].startswith("palabra") for f in fr)
    assert fr[0].texto.split()[-1] in fr[1].texto[:TRASLAPE + 20]

def test_pagina_del_primer_parrafo():
    fr = fragmentar([Pagina(1, "Uno."), Pagina(2, "Dos.")])
    assert fr[0].pagina == 1 and [f.posicion for f in fr] == list(range(len(fr)))

def test_sin_texto_no_genera_fragmentos():
    assert fragmentar([Pagina(0, "  \n\n ")]) == []
```

- [ ] **Step 2: Correr y verificar que fallan.** Run: `uv run pytest tests/test_conocimiento_fragmentar.py -v`. Expected: FAIL.
- [ ] **Step 3: Implementar** `fragmentar.py` según el algoritmo.
- [ ] **Step 4: Verificar.** Run: `uv run pytest tests/test_conocimiento_fragmentar.py -v`. Expected: PASS.
- [ ] **Step 5: Commit y push.** Mensaje: "Fragmentación de texto legal por artículos con tamaño y traslape".

### Task 4: Embeddings locales y almacén Chroma por usuario

**Files:**
- Create: `app/conocimiento/embeddings.py`, `app/conocimiento/almacen.py`, `tests/test_conocimiento_almacen.py`
- Modify: `tests/helpers.py` (agrega `EmbeddingsFalsos`)

**Interfaces:**
- Consumes: `Fragmento` (Task 3) y `resolver` (Task 1).
- Produces:
  - `embeddings.py`:
    - `class Embeddings(Protocol): def embeber(self, textos: list[str]) -> list[list[float]]: ...`;
    - `class EmbeddingsFastEmbed`, con `__init__(self, modelo: str, cache: Path)`. Crea `fastembed.TextEmbedding(model_name=modelo, cache_dir=str(cache), threads=1)` **perezosamente**, en la primera llamada a `embeber`, protegida con un `threading.Lock`. Devuelve listas de `float`.
  - `almacen.py`, con `class Almacen`:
    - `__init__(self, ruta: Path, embeddings: Embeddings)`: un `chromadb.PersistentClient(path=str(ruta), settings=chromadb.Settings(anonymized_telemetry=False))`;
    - `_coleccion(self, usuario_id: int)`: `get_or_create_collection(f"usuario_{usuario_id}", ...)` con distancia coseno y `embedding_function=None`, porque los embeddings se calculan aquí;
    - `guardar(self, usuario_id: int, archivo_id: int, nombre_archivo: str, fragmentos: list[Fragmento]) -> int`: `upsert` por lotes de 32, con los ids y metadatos de Global Constraints; devuelve cuántos guardó;
    - `borrar_archivo(self, usuario_id: int, archivo_id: int) -> None`: borra con `where={"archivo_id": archivo_id}`;
    - `consultar(self, usuario_id: int, consulta: str, k: int, archivos: list[int]) -> list[dict]`. Si `archivos` está vacío o la consulta queda vacía tras `strip()`, devuelve `[]` sin tocar Chroma. Si no, consulta con `where={"archivo_id": {"$in": archivos}}` y devuelve dicts con `texto`, los metadatos y `score = 1 - distancia`, ordenados de mayor a menor.
  - `tests/helpers.py`: `class EmbeddingsFalsos` con `embeber`, que es una bolsa de palabras: minúsculas, sin acentos (`unicodedata`), tokens alfanuméricos, cada token a `hash md5 % 64` y el vector de 64 dimensiones normalizado. Es determinista y no usa la red.

- [ ] **Step 1: Escribir las pruebas que fallan** (con `Almacen(tmp_path / "chroma", EmbeddingsFalsos())`):

```python
def test_guardar_y_consultar_relevante(almacen):
    fr = [Fragmento(0, "El arrendatario pagará la renta mensual", 1, "Artículo 3"),
          Fragmento(1, "La vigencia del contrato es de un año", 1, "Artículo 4")]
    assert almacen.guardar(1, 10, "contrato.pdf", fr) == 2
    r = almacen.consultar(1, "¿Cuánto es la renta mensual?", 1, [10])
    assert r[0]["articulo"] == "Artículo 3" and r[0]["nombre_archivo"] == "contrato.pdf" and 0 < r[0]["score"] <= 1

def test_aislamiento_entre_usuarios(almacen):
    almacen.guardar(1, 10, "a.pdf", [Fragmento(0, "secreto del usuario uno", 0, "")])
    almacen.guardar(2, 20, "b.pdf", [Fragmento(0, "texto del usuario dos", 0, "")])
    assert all(x["usuario_id"] == 2 for x in almacen.consultar(2, "secreto usuario uno", 5, [10, 20]))

def test_upsert_no_duplica_y_borrar(almacen):
    fr = [Fragmento(0, "uno", 0, ""), Fragmento(1, "dos", 0, "")]
    almacen.guardar(1, 10, "a.pdf", fr); almacen.guardar(1, 10, "a.pdf", fr)
    assert len(almacen.consultar(1, "uno dos", 10, [10])) == 2
    almacen.borrar_archivo(1, 10)
    assert almacen.consultar(1, "uno dos", 10, [10]) == []

def test_sin_archivos_o_consulta_vacia(almacen):
    assert almacen.consultar(1, "algo", 5, []) == [] and almacen.consultar(1, "   ", 5, [10]) == []
```

  La prueba de aislamiento pasa `[10, 20]` a propósito: aunque los ids de archivo se filtren mal, la colección de otro usuario nunca se consulta.

- [ ] **Step 2: Correr y verificar que fallan.** Run: `uv run pytest tests/test_conocimiento_almacen.py -v`. Expected: FAIL.
- [ ] **Step 3: Implementar** `embeddings.py`, `almacen.py` y `EmbeddingsFalsos`.
- [ ] **Step 4: Verificar.**
  - `uv run pytest tests/test_conocimiento_almacen.py -v`: PASS, sin warnings de telemetría.
  - Prueba manual, sin commitear: `uv run python -c "from pathlib import Path; from app.conocimiento.embeddings import EmbeddingsFastEmbed; e=EmbeddingsFastEmbed('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', Path('data/modelos')); print(len(e.embeber(['Artículo 1'])[0]))"` imprime `384`.
- [ ] **Step 5: Commit y push.** Mensaje: "Embeddings ONNX locales y almacén Chroma con una colección por usuario".

### Task 5: Servicio de conocimiento (subir, procesar, listar, borrar, buscar)

**Files:**
- Create: `app/conocimiento/servicio.py`, `tests/test_conocimiento_servicio.py`
- Modify: `app/main.py` (crea `app.state.almacen` y `app.state.ruta_archivos`, y un `lifespan` que llama a `marcar_interrumpidos`), `tests/conftest.py` (sobrescribe `app.state.almacen` con `Almacen(tmp_path / "chroma", EmbeddingsFalsos())` y `app.state.ruta_archivos` con `tmp_path / "archivos"`)

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces:
  - `TAMANO_MAXIMO = 20_971_520`;
  - excepciones con los mensajes exactos de Global Constraints: `ArchivoDemasiadoGrande`, `TipoNoPermitido` (reexportada de `extraer`), `ArchivoDuplicado` y `NoEncontrado` (reutiliza la de `app.documentos.servicio`, para que el manejador global responda 404);
  - `subir(db, usuario_id: int, nombre_original: str, origen: BinaryIO, ruta_archivos: Path) -> ArchivoConocimiento`:
    1. copia el contenido a `ruta_archivos/<usuario_id>/<uuid>.tmp` en bloques de 1 MB, calcula el SHA-256 al vuelo y aborta con `ArchivoDemasiadoGrande` al pasar de `TAMANO_MAXIMO`, borrando el temporal;
    2. detecta el tipo con `detectar_tipo` (si falla, borra el temporal);
    3. si ya existe el mismo `sha256` para el usuario, lanza `ArchivoDuplicado` y borra el temporal;
    4. renombra el temporal a la extensión real, registra con estado `procesando` y hace `commit`;
    5. `nombre_original` se recorta a 255 caracteres.
  - `procesar(SessionLocal, almacen: Almacen, archivo_id: int) -> None`: `def` normal, para `BackgroundTasks`.
    1. Toma el `threading.Lock` de ingesta.
    2. Abre su propia sesión. Si el archivo ya no existe, sale sin hacer nada.
    3. Extrae, fragmenta y guarda en Chroma.
    4. Vuelve a leer el registro. Si se borró durante el proceso, llama a `almacen.borrar_archivo` y sale.
    5. Si sigue, marca `listo` con `num_fragmentos` y hace `commit`.
    6. Ante `SinTexto`, marca `error` con su mensaje. Ante cualquier otra excepción, marca `error` con `"no se pudo procesar el archivo"` y registra la excepción con `logger.exception`. Nunca relanza.
  - `listar(db, usuario_id) -> list[ArchivoConocimiento]`, del más reciente al más antiguo.
  - `obtener(db, usuario_id, archivo_id) -> ArchivoConocimiento`, que lanza `NoEncontrado` si no existe o es ajeno.
  - `borrar(db, almacen, usuario_id, archivo_id) -> None`: borra el registro (`commit`), sus fragmentos de Chroma y el archivo en disco (`missing_ok=True`).
  - `buscar(db, almacen, usuario_id: int, consulta: str, k: int = 5, umbral: float = 0.0) -> list[Resultado]`:
    - `@dataclass Resultado(texto: str, archivo_id: int, nombre_archivo: str, pagina: int, articulo: str, score: float, referencia: str)`;
    - solo considera los ids de archivos `listo` del usuario, consultados en SQL;
    - descarta los resultados con `score < umbral`;
    - `referencia` es `"<nombre>, <articulo>"` si hay artículo, `"<nombre>, página <n>"` si `pagina > 0`, o solo `"<nombre>"`.
  - `marcar_interrumpidos(db) -> int`: los registros en `procesando` pasan a `error` con `"procesamiento interrumpido"`; devuelve cuántos cambió.

- [ ] **Step 1: Escribir las pruebas que fallan.** Usa `app.state.SessionLocal`, `app.state.almacen` y `app.state.ruta_archivos`, más un helper local `subir_txt(db, app, u, texto, nombre="a.txt")` que llama a `subir` con `io.BytesIO`:

```python
def test_subir_procesar_y_buscar(app, db):
    u = crear(db, "a@x.com")
    a = subir_txt(db, app, u, "Artículo 1. El arrendatario pagará la renta mensual.\n\nArtículo 2. Vigencia de un año.")
    assert a.estado == "procesando" and Path(a.ruta_disco).suffix == ".txt"
    procesar(app.state.SessionLocal, app.state.almacen, a.id)
    db.refresh(a); assert a.estado == "listo" and a.num_fragmentos == 2
    r = buscar(db, app.state.almacen, u.id, "renta mensual", k=1)
    assert r[0].referencia == "a.txt, Artículo 1"

def test_duplicado_409_sin_segundo_registro(app, db):
    u = crear(db, "a@x.com"); subir_txt(db, app, u, "Hola")
    with pytest.raises(ArchivoDuplicado):
        subir_txt(db, app, u, "Hola", nombre="otro.txt")
    assert len(listar(db, u.id)) == 1

def test_demasiado_grande_no_deja_archivo(app, db, monkeypatch):
    monkeypatch.setattr("app.conocimiento.servicio.TAMANO_MAXIMO", 10)
    u = crear(db, "a@x.com")
    with pytest.raises(ArchivoDemasiadoGrande):
        subir_txt(db, app, u, "x" * 11)
    assert not any(app.state.ruta_archivos.rglob("*.*"))

def test_pdf_sin_texto_queda_en_error(app, db):
    u = crear(db, "a@x.com")
    a = subir(db, u.id, "e.pdf", io.BytesIO(pdf_minimo([""])), app.state.ruta_archivos)
    procesar(app.state.SessionLocal, app.state.almacen, a.id)
    db.refresh(a); assert a.estado == "error" and a.mensaje_error == "el PDF no contiene texto (¿escaneado?)"

def test_procesar_archivo_borrado_no_falla(app, db):
    u = crear(db, "a@x.com"); a = subir_txt(db, app, u, "Hola mundo")
    borrar(db, app.state.almacen, u.id, a.id)
    procesar(app.state.SessionLocal, app.state.almacen, a.id)
    assert buscar(db, app.state.almacen, u.id, "hola") == []

def test_buscar_ignora_procesando_y_ajenos(app, db):
    a_u = crear(db, "a@x.com"); b_u = crear(db, "b@x.com")
    pa = subir_txt(db, app, a_u, "secreto de A"); procesar(app.state.SessionLocal, app.state.almacen, pa.id)
    subir_txt(db, app, b_u, "pendiente de B")  # sigue en procesando
    assert buscar(db, app.state.almacen, b_u.id, "secreto de A pendiente de B") == []

def test_marcar_interrumpidos(app, db):
    u = crear(db, "a@x.com"); a = subir_txt(db, app, u, "Hola")
    assert marcar_interrumpidos(db) == 1
    db.refresh(a); assert (a.estado, a.mensaje_error) == ("error", "procesamiento interrumpido")

def test_obtener_ajeno_404(app, db):
    a_u = crear(db, "a@x.com"); b_u = crear(db, "b@x.com"); a = subir_txt(db, app, a_u, "Hola")
    with pytest.raises(NoEncontrado):
        obtener(db, b_u.id, a.id)
```

- [ ] **Step 2: Correr y verificar que fallan.** Run: `uv run pytest tests/test_conocimiento_servicio.py -v`. Expected: FAIL.
- [ ] **Step 3: Implementar** `servicio.py`, los cambios en `app/main.py` (con `Almacen(resolver(settings.chroma_path), EmbeddingsFastEmbed(settings.embeddings_modelo, resolver(settings.modelos_path)))`; el modelo no se carga hasta el primer `embeber`) y la fixture de `conftest.py`.
- [ ] **Step 4: Verificar.** Run: `uv run pytest -q`. Expected: todas pasan y la salida queda limpia.
- [ ] **Step 5: Commit y push.** Mensaje: "Servicio de conocimiento: subida validada, ingesta en segundo plano y búsqueda aislada".

### Task 6: Página de conocimiento y rutas

**Files:**
- Create: `app/conocimiento/rutas.py`, `app/web/plantillas/conocimiento.html`, `app/web/plantillas/_fila_archivo.html`, `app/web/plantillas/_resultados.html`, `tests/test_conocimiento_rutas.py`
- Modify: `app/main.py` (incluye el router y mapea `ArchivoDemasiadoGrande`, `TipoNoPermitido` y `ArchivoDuplicado`), `app/web/plantillas/base.html` (enlace "Conocimiento" en la barra), `app/web/estaticos/estilos.css` (estilos mínimos de la tabla y los estados), `deploy/nginx-editor.conf` (`client_max_body_size 21m;` a nivel de `server`, con un comentario; el límite de 2 MB de documentos ya lo aplica la app)

**Interfaces:**
- Consumes: el servicio (Task 5) y `usuario_actual`.
- Produces (todas las rutas con `usuario_actual`; un archivo ajeno responde 404):
  - `GET /conocimiento`: página con el formulario de subida (`hx-post`, `hx-encoding="multipart/form-data"`, campo `archivo`, `accept=".pdf,.docx,.txt"`), la tabla de archivos (nombre, tipo, tamaño en KB o MB, estado, fragmentos, mensaje de error, botón Borrar con `hx-delete` y `hx-confirm`) y una caja "Probar búsqueda".
  - `POST /conocimiento/archivos`:
    - `UploadFile` llamado `archivo`; pasa `archivo.file` y `archivo.filename` a `subir` y agrega `procesar(request.app.state.SessionLocal, request.app.state.almacen, id)` a `BackgroundTasks`;
    - responde 200 con el fragmento `_fila_archivo.html`, que HTMX inserta al principio de la tabla;
    - los errores de subida responden 400 o 409 con el mensaje en un fragmento `<p class="error" role="alert">…</p>` dirigido a `#mensaje-subida`; usa `hx-target-error` o `HX-Retarget`, a elección del implementador.
  - `GET /conocimiento/archivos/{id}/fila`: el fragmento de la fila. Mientras el estado sea `procesando`, la fila lleva `hx-get` a sí misma con `hx-trigger="every 2s"` y `hx-swap="outerHTML"`; en `listo` o `error`, no lleva trigger y el polling se detiene.
  - `DELETE /conocimiento/archivos/{id}`: 200 vacío.
  - `GET /conocimiento/buscar?q=`: el fragmento `_resultados.html` con hasta 5 resultados de `buscar(..., umbral=settings.umbral_similitud)` (referencia, score con 2 decimales y texto recortado a 400 caracteres). Si no hay resultados, muestra "Sin resultados en tu conocimiento.".

- [ ] **Step 1: Escribir las pruebas que fallan:**

```python
def test_subir_y_ver_listo(client, db):
    crear(db, "a@x.com"); entrar(client, "a@x.com")
    r = client.post("/conocimiento/archivos", files={"archivo": ("ley.txt", "Artículo 1. Renta mensual.".encode(), "text/plain")})
    assert r.status_code == 200 and "ley.txt" in r.text
    assert "listo" in client.get("/conocimiento").text  # BackgroundTasks corre al terminar la petición en TestClient

def test_fila_deja_de_hacer_polling(client, db, app):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com")
    a = subir(db, u.id, "a.txt", io.BytesIO(b"Hola"), app.state.ruta_archivos)
    assert 'every 2s' in client.get(f"/conocimiento/archivos/{a.id}/fila").text
    procesar(app.state.SessionLocal, app.state.almacen, a.id)
    assert 'every 2s' not in client.get(f"/conocimiento/archivos/{a.id}/fila").text

def test_tipo_disfrazado_400(client, db):
    crear(db, "a@x.com"); entrar(client, "a@x.com")
    r = client.post("/conocimiento/archivos", files={"archivo": ("x.pdf", b"MZ\x90\x00binario", "application/pdf")})
    assert r.status_code == 400 and "Tipo de archivo no permitido" in r.text

def test_aislamiento_rutas(client, db, app):
    crear(db, "a@x.com"); b = crear(db, "b@x.com")
    a = subir(db, b.id, "b.txt", io.BytesIO(b"secreto de B"), app.state.ruta_archivos)
    procesar(app.state.SessionLocal, app.state.almacen, a.id)
    entrar(client, "a@x.com")
    assert client.get(f"/conocimiento/archivos/{a.id}/fila").status_code == 404
    assert client.delete(f"/conocimiento/archivos/{a.id}").status_code == 404
    assert "b.txt" not in client.get("/conocimiento").text
    assert "secreto" not in client.get("/conocimiento/buscar", params={"q": "secreto de B"}).text

def test_buscar_muestra_referencia(client, db):
    crear(db, "a@x.com"); entrar(client, "a@x.com")
    client.post("/conocimiento/archivos", files={"archivo": ("ley.txt", "Artículo 7. Pago de renta mensual.".encode(), "text/plain")})
    assert "ley.txt, Artículo 7" in client.get("/conocimiento/buscar", params={"q": "renta"}).text

def test_requiere_sesion(client):
    assert client.get("/conocimiento", headers={"Accept": "text/html"}, follow_redirects=False).status_code == 303
```

- [ ] **Step 2: Correr y verificar que fallan.** Run: `uv run pytest tests/test_conocimiento_rutas.py -v`. Expected: FAIL.
- [ ] **Step 3: Implementar** las rutas, las plantillas, el enlace en la barra, los estilos y el cambio en Nginx.
- [ ] **Step 4: Verificar.**
  - `uv run pytest -q`: todas pasan.
  - Con `uv run uvicorn app.main:app --reload`: subir un TXT y un DOCX reales desde `/conocimiento`, ver el paso de "procesando" a "listo" sin recargar y buscar una frase. La primera ingesta descarga el modelo a `data/modelos` (unos 220 MB).
- [ ] **Step 5: Commit y push.** Mensaje: "Página de conocimiento: subida, estados con polling, borrado y prueba de búsqueda".

### Task 7: Calibración del umbral y despliegue

**Files:**
- Create: `scripts/calibrar_busqueda.py`, `scripts/descargar_modelo.py`
- Modify: `app/config.py` (default de `umbral_similitud`), `deploy/actualizar.sh` (descarga el modelo antes de reiniciar), `CLAUDE.md` (módulo `conocimiento/`, comandos nuevos y la regla de un worker, que ahora también exige la ingesta), `docs/superpowers/ESTADO.md`

**Interfaces:**
- Consumes: `EmbeddingsFastEmbed` y `Almacen` (Task 4), y `fragmentar` (Task 3).
- Produces:
  - `scripts/descargar_modelo.py`: instancia `EmbeddingsFastEmbed` con los settings y llama a `embeber(["prueba"])`; imprime `modelo listo (384 dimensiones)`.
  - `scripts/calibrar_busqueda.py`:
    1. arma un corpus propio, escrito para el script (seis artículos ficticios de un contrato de arrendamiento y de una ley de procedimiento, de 2 a 4 oraciones cada uno), y lo indexa con el modelo real en un `Almacen` sobre un directorio temporal;
    2. corre diez preguntas en español, cada una con el artículo que debe salir primero, más cuatro preguntas sin respuesta en el corpus (p. ej. sobre derecho marítimo);
    3. imprime por pregunta el score del primer resultado y si acertó, la exactitud top-1, el mínimo score de los aciertos (`min_acierto`) y el máximo score de las preguntas sin respuesta (`max_irrelevante`);
    4. imprime `umbral_recomendado = round((min_acierto + max_irrelevante) / 2, 2)` si `min_acierto > max_irrelevante`, o `0.0` con un aviso si se traslapan.

- [ ] **Step 1: Escribir y correr la calibración.** Run: `uv run python scripts/calibrar_busqueda.py`. Expected: exactitud top-1 ≥ 8/10 y un `umbral_recomendado`. Si la exactitud es menor, no se cambia de modelo en esta tarea: se reporta como DONE_WITH_CONCERNS con la salida completa.
- [ ] **Step 2: Fijar el umbral.** Pon el `umbral_recomendado` impreso como default de `umbral_similitud` en `app/config.py` y pega la salida literal del script en el informe de la tarea.
- [ ] **Step 3: Despliegue.**
  - En `deploy/actualizar.sh`, después de `uv sync`, agrega `sudo -u editor .venv/bin/python scripts/descargar_modelo.py`.
  - Actualiza `CLAUDE.md` y `ESTADO.md`. `ESTADO.md` queda con el Plan 2 cerrado y el Plan 3 como siguiente.
- [ ] **Step 4: Verificar.** Run: `uv run pytest -q` (todas pasan) y `uv run python scripts/descargar_modelo.py` (imprime `modelo listo (384 dimensiones)`).
- [ ] **Step 5: Commit y push.** Mensaje: "Calibración del umbral de búsqueda, descarga del modelo en el despliegue y documentación". Después, el controlador corre `deploy/actualizar.sh` en el droplet, reinstala `deploy/nginx-editor.conf` y comprueba allí una subida real y su memoria (`free -h`) con `/conocimiento`.
