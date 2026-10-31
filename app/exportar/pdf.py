"""Conversión de .docx a PDF con LibreOffice y cabecera de descarga."""

import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import unicodedata
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parent.parent.parent
PERFIL_LIBREOFFICE = RAIZ / "data" / "lo_perfil"
SOFFICE_MACOS = "/Applications/LibreOffice.app/Contents/MacOS/soffice"

# Una sola conversión a la vez: LibreOffice con un perfil compartido no admite concurrencia.
# El cerrojo es por proceso: exige un solo worker de uvicorn (el despliegue usa --workers 1).
_CERROJO = threading.Lock()
_PROHIBIDOS = re.compile(r'[/\\"\x00-\x1f\x7f]')


class ErrorConversionPDF(Exception):
    pass


def _buscar_soffice() -> str | None:
    ruta = shutil.which("soffice")
    if ruta:
        return ruta
    return SOFFICE_MACOS if Path(SOFFICE_MACOS).exists() else None


def soffice_disponible() -> bool:
    return _buscar_soffice() is not None


def _matar_grupo(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def docx_a_pdf(docx: bytes, timeout: int = 60) -> bytes:
    soffice = _buscar_soffice()
    if soffice is None:
        raise ErrorConversionPDF("LibreOffice no está instalado.")
    with tempfile.TemporaryDirectory() as tmp:
        entrada = Path(tmp) / "doc.docx"
        entrada.write_bytes(docx)
        with _CERROJO:
            try:
                PERFIL_LIBREOFFICE.mkdir(parents=True, exist_ok=True)
                # Sesión propia: soffice lanza hijos (oosplash, soffice.bin) que hay que matar juntos.
                proc = subprocess.Popen(
                    [
                        soffice,
                        f"-env:UserInstallation={PERFIL_LIBREOFFICE.resolve().as_uri()}",
                        "--headless",
                        "--norestore",
                        "--convert-to", "pdf",
                        "--outdir", tmp,
                        str(entrada),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
            except OSError as e:
                raise ErrorConversionPDF(f"No se pudo lanzar soffice: {e}") from e
            try:
                _, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as e:
                _matar_grupo(proc)
                raise ErrorConversionPDF(f"Tiempo agotado ({timeout} s) al convertir a PDF.") from e
            except BaseException:
                _matar_grupo(proc)
                raise
            if proc.returncode != 0:
                detalle = err.decode(errors="replace").strip()[-500:]
                raise ErrorConversionPDF(f"soffice terminó con código {proc.returncode}: {detalle}")
        salida = Path(tmp) / "doc.pdf"
        if not salida.exists():
            raise ErrorConversionPDF("LibreOffice no produjo el PDF.")
        return salida.read_bytes()


def disposicion_adjunto(titulo: str, extension: str) -> str:
    limpio = _PROHIBIDOS.sub("", titulo).strip() or "documento"
    nombre = f"{limpio}.{extension}"
    ascii_ = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    # NFKD convierte caracteres de ancho completo en " / \\: limpiar de nuevo.
    ascii_ = _PROHIBIDOS.sub("", ascii_)
    if not ascii_.removesuffix(f".{extension}").strip():
        ascii_ = f"documento.{extension}"
    return f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre, safe='')}"
