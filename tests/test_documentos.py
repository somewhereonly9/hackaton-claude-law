from app.documentos import servicio
from tests.helpers import crear, entrar


def test_crud_basico(client, db):
    crear(db, "a@x.com"); entrar(client, "a@x.com")
    r = client.post("/documentos", follow_redirects=False)
    assert r.status_code == 303
    doc_id = int(r.headers["location"].rsplit("/", 1)[1])
    contenido = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hola"}]}]}
    r = client.put(f"/documentos/{doc_id}/contenido", json=contenido)
    assert r.status_code == 200 and r.json()["ok"] is True and "actualizado_en" in r.json()
    assert "Documento sin título" in client.get("/documentos").text
    client.post(f"/documentos/{doc_id}/titulo", data={"titulo": "Contrato"})
    assert "Contrato" in client.get("/documentos").text
    assert client.get(f"/documentos/{doc_id}").status_code == 200
    assert client.delete(f"/documentos/{doc_id}").status_code == 200
    assert client.get(f"/documentos/{doc_id}").status_code == 404


def test_aislamiento_entre_usuarios(client, db):
    crear(db, "a@x.com"); b = crear(db, "b@x.com")
    doc_b = servicio.crear(db, b.id, "Secreto de B")
    entrar(client, "a@x.com")
    assert "Secreto de B" not in client.get("/documentos").text
    assert client.get(f"/documentos/{doc_b.id}").status_code == 404
    assert client.put(f"/documentos/{doc_b.id}/contenido", json=servicio.CONTENIDO_VACIO).status_code == 404
    assert client.post(f"/documentos/{doc_b.id}/titulo", data={"titulo": "x"}).status_code == 404
    assert client.delete(f"/documentos/{doc_b.id}").status_code == 404


def test_contenido_invalido_no_se_guarda(client, db):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com")
    d = servicio.crear(db, u.id)
    assert client.put(f"/documentos/{d.id}/contenido", json={"type": "otro"}).status_code == 422
    assert client.put(f"/documentos/{d.id}/contenido", content=b"{no es json", headers={"content-type": "application/json"}).status_code == 422
    db.refresh(d); assert d.contenido == servicio.CONTENIDO_VACIO


def test_contenido_demasiado_grande(client, db):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com")
    d = servicio.crear(db, u.id)
    grande = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x" * 2_200_000}]}]}
    assert client.put(f"/documentos/{d.id}/contenido", json=grande).status_code == 413


def test_titulo_vacio_se_rechaza(client, db):
    u = crear(db, "a@x.com"); entrar(client, "a@x.com")
    d = servicio.crear(db, u.id)
    assert client.post(f"/documentos/{d.id}/titulo", data={"titulo": "   "}).status_code == 422
    assert client.post(f"/documentos/{d.id}/titulo", data={"titulo": "x" * 201}).status_code == 422


def test_listar_ordena_por_actualizacion(db):
    u = crear(db, "a@x.com")
    viejo = servicio.crear(db, u.id, "Viejo")
    nuevo = servicio.crear(db, u.id, "Nuevo")
    servicio.guardar_contenido(db, u.id, viejo.id, {"type": "doc", "content": [{"type": "paragraph"}]})
    from sqlalchemy import text
    db.execute(text("UPDATE documentos SET actualizado_en = '2020-01-01 00:00:00' WHERE id = :i"), {"i": nuevo.id})
    db.commit()
    assert [d.titulo for d in servicio.listar(db, u.id)] == ["Viejo", "Nuevo"]
