from tests.helpers import crear, entrar


def test_no_admin_recibe_404(client, db):
    crear(db, "a@x.com"); entrar(client, "a@x.com")
    assert client.get("/admin/usuarios").status_code == 404
    assert client.post("/admin/usuarios", data={"email": "n@x.com", "nombre": "N", "password": "secreta123"}).status_code == 404


def test_admin_crea_usuario_que_puede_entrar(client, db):
    crear(db, "admin@x.com", es_admin=True); entrar(client, "admin@x.com")
    r = client.post("/admin/usuarios", data={"email": "n@x.com", "nombre": "N", "password": "secreta123"}, follow_redirects=False)
    assert r.status_code == 303
    client.post("/logout"); entrar(client, "n@x.com")


def test_admin_rechaza_email_duplicado(client, db):
    crear(db, "admin@x.com", es_admin=True); crear(db, "n@x.com"); entrar(client, "admin@x.com")
    r = client.post("/admin/usuarios", data={"email": "N@X.com", "nombre": "N", "password": "secreta123"})
    assert r.status_code == 400 and "ya existe" in r.text


def test_admin_restablece_contrasena(client, db):
    crear(db, "admin@x.com", es_admin=True); u = crear(db, "n@x.com"); entrar(client, "admin@x.com")
    client.post(f"/admin/usuarios/{u.id}/contrasena", data={"password": "nueva12345"})
    client.post("/logout"); entrar(client, "n@x.com", "nueva12345")


def test_admin_no_se_desactiva_a_si_mismo(client, db):
    admin = crear(db, "admin@x.com", es_admin=True); entrar(client, "admin@x.com")
    r = client.post(f"/admin/usuarios/{admin.id}/activo", data={"activo": "false"})
    assert r.status_code == 400


def test_usuario_inexistente_404(client, db):
    crear(db, "admin@x.com", es_admin=True); entrar(client, "admin@x.com")
    assert client.post("/admin/usuarios/99999/activo", data={"activo": "false"}).status_code == 404


def test_admin_lista_usuarios(client, db):
    crear(db, "admin@x.com", es_admin=True); crear(db, "n@x.com"); entrar(client, "admin@x.com")
    r = client.get("/admin/usuarios")
    assert r.status_code == 200 and "n@x.com" in r.text


def test_contrasena_corta_400(client, db):
    crear(db, "admin@x.com", es_admin=True); u = crear(db, "n@x.com"); entrar(client, "admin@x.com")
    r = client.post(f"/admin/usuarios/{u.id}/contrasena", data={"password": "corta"})
    assert r.status_code == 400 and "8 caracteres" in r.text


def test_admin_desactiva_usuario(client, db):
    crear(db, "admin@x.com", es_admin=True); u = crear(db, "n@x.com"); entrar(client, "admin@x.com")
    r = client.post(f"/admin/usuarios/{u.id}/activo", data={"activo": "false"}, follow_redirects=False)
    assert r.status_code == 303
    client.post("/logout")
    assert client.post("/login", data={"email": "n@x.com", "password": "secreta123"}).status_code == 400
