import pytest

from app.documentos import servicio
from app.exportar.pdf import ErrorConversionPDF, disposicion_adjunto, soffice_disponible
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
    assert "\r" not in h and "\n" not in h and "\\" not in h.split("filename*=")[0].replace('\\"', "")
    assert h.startswith('attachment; filename="')


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
