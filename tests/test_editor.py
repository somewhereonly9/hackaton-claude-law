from app.documentos import servicio
from tests.helpers import crear, entrar


def test_editor_incluye_contenido_escapado(client, db):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com")
    d = servicio.crear(db, u.id)
    servicio.guardar_contenido(db, u.id, d.id, {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "</script><b>x"}]}]})
    r = client.get(f"/documentos/{d.id}")
    assert r.status_code == 200
    assert 'id="editor"' in r.text and "editor.js" in r.text
    assert "</script><b>x" not in r.text
    assert 'id="contenido-inicial"' in r.text
    assert "\\u003c/script\\u003e\\u003cb\\u003ex" in r.text


def test_editor_de_documento_ajeno_es_404(client, db):
    u = crear(db, "a@x.com")
    crear(db, "b@x.com"); entrar(client, "b@x.com")
    d = servicio.crear(db, u.id)
    assert client.get(f"/documentos/{d.id}").status_code == 404
