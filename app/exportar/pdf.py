"""Conversión de .docx a PDF con LibreOffice y cabecera de descarga."""

import re
import shutil
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


def docx_a_pdf(docx: bytes, timeout: int = 60) -> bytes:
    soffice = _buscar_soffice()
    if soffice is None:
        raise ErrorConversionPDF("LibreOffice no está instalado.")
    with tempfile.TemporaryDirectory() as tmp:
        entrada = Path(tmp) / "doc.docx"
        entrada.write_bytes(docx)
        try:
            with _CERROJO:
                PERFIL_LIBREOFFICE.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    [
                        soffice,
                        f"-env:UserInstallation={PERFIL_LIBREOFFICE.resolve().as_uri()}",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", tmp,
                        str(entrada),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=timeout,
                )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            raise ErrorConversionPDF("Falló la conversión a PDF.") from e
        salida = Path(tmp) / "doc.pdf"
        if not salida.exists():
            raise ErrorConversionPDF("LibreOffice no produjo el PDF.")
        return salida.read_bytes()


def disposicion_adjunto(titulo: str, extension: str) -> str:
    limpio = _PROHIBIDOS.sub("", titulo).strip() or "documento"
    nombre = f"{limpio}.{extension}"
    ascii_ = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    if not ascii_.removesuffix(f".{extension}").strip():
        ascii_ = f"documento.{extension}"
    return f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre, safe='')}"
