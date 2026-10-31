import os
import time

import pytest

from app.documentos import servicio
from app.exportar import pdf
from app.exportar.pdf import ErrorConversionPDF, docx_a_pdf, disposicion_adjunto, soffice_disponible
from tests.helpers import crear, entrar


def test_descarga_docx(client, db):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com"); d = servicio.crear(db, u.id, "Contrato")
    r = client.get(f"/documentos/{d.id}/exportar.docx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def test_nombre_archivo_con_acentos():
    h = disposicion_adjunto("Contrato — Ñandú / 2026", "docx")
    assert "filename*=UTF-8''" in h and "%C3%91and%C3%BA" in h and "/" not in h.split("filename*=")[1].replace("%2F", "")


def test_nombre_archivo_sin_inyeccion_de_cabeceras():
    h = disposicion_adjunto('a"b\r\nX-Falso: 1\\c', "docx")
    assert "\r" not in h and "\n" not in h
    assert h.split("; filename*=")[0].count('"') == 2
    assert h.startswith('attachment; filename="')


def test_nombre_archivo_ancho_completo():
    h = disposicion_adjunto("a＂b／c＼d", "docx")
    ascii_ = h.split("; filename*=")[0]
    assert ascii_.count('"') == 2 and "/" not in ascii_ and "\\" not in ascii_


def test_nombre_archivo_vacio_usa_documento():
    assert 'filename="documento.docx"' in disposicion_adjunto("//\x00", "docx")


def test_exportar_ajeno_404(client, db):
    crear(db, "a@x.com"); b = crear(db, "b@x.com"); d = servicio.crear(db, b.id)
    entrar(client, "a@x.com")
    assert client.get(f"/documentos/{d.id}/exportar.docx").status_code == 404
    assert client.get(f"/documentos/{d.id}/exportar.pdf").status_code == 404


def test_pdf_falla_con_503(client, db, monkeypatch):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com"); d = servicio.crear(db, u.id)
    monkeypatch.setattr("app.exportar.rutas.docx_a_pdf", lambda *a, **k: (_ for _ in ()).throw(ErrorConversionPDF("x")))
    r = client.get(f"/documentos/{d.id}/exportar.pdf")
    assert r.status_code == 503 and ".docx" in r.text


@pytest.mark.skipif(not soffice_disponible(), reason="LibreOffice no instalado")
def test_pdf_real(client, db):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com"); d = servicio.crear(db, u.id)
    r = client.get(f"/documentos/{d.id}/exportar.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_timeout_mata_el_grupo_y_libera_el_cerrojo(tmp_path, monkeypatch):
    pidfile = tmp_path / "hijo.pid"
    falso = tmp_path / "soffice"
    falso.write_text(f"#!/bin/sh\nsleep 60 &\necho $! > {pidfile}\nwait\n")
    falso.chmod(0o755)
    monkeypatch.setattr(pdf, "_buscar_soffice", lambda: str(falso))
    monkeypatch.setattr(pdf, "PERFIL_LIBREOFFICE", tmp_path / "perfil")
    inicio = time.monotonic()
    with pytest.raises(ErrorConversionPDF):
        docx_a_pdf(b"x", timeout=1)
    assert time.monotonic() - inicio < 10
    assert not pdf._CERROJO.locked()
    hijo = int(pidfile.read_text())
    for _ in range(50):
        try:
            os.kill(hijo, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("el hijo de soffice sigue vivo")


def test_salida_distinta_de_cero_incluye_stderr(tmp_path, monkeypatch):
    falso = tmp_path / "soffice"
    falso.write_text("#!/bin/sh\necho boom >&2\nexit 3\n")
    falso.chmod(0o755)
    monkeypatch.setattr(pdf, "_buscar_soffice", lambda: str(falso))
    monkeypatch.setattr(pdf, "PERFIL_LIBREOFFICE", tmp_path / "perfil")
    with pytest.raises(ErrorConversionPDF, match="código 3.*boom"):
        docx_a_pdf(b"x")
    assert not pdf._CERROJO.locked()
