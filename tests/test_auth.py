from app.cli import crear_admin
from app.usuarios.servicio import cambiar_activo
from tests.helpers import crear, entrar


def test_login_correcto_redirige(client, db):
    crear(db, "a@x.com")
    r = client.post("/login", data={"email": "A@x.com", "password": "secreta123"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/documentos"


def test_login_incorrecto(client, db):
    crear(db, "a@x.com")
    r = client.post("/login", data={"email": "a@x.com", "password": "mala12345"})
    assert r.status_code == 400 and "Correo o contraseña incorrectos" in r.text


def test_sin_sesion_redirige_a_login(client):
    r = client.get("/documentos", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_sin_sesion_json_401(client):
    r = client.get("/documentos", headers={"accept": "application/json"})
    assert r.status_code == 401 and r.json() == {"detalle": "no autenticado"}


def test_usuario_desactivado_pierde_la_sesion(client, db):
    admin = crear(db, "admin@x.com", es_admin=True)
    u = crear(db, "a@x.com")
    entrar(client, "a@x.com")
    cambiar_activo(db, admin, u.id, False)
    r = client.get("/documentos", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303


def test_logout(client, db):
    crear(db, "a@x.com")
    entrar(client, "a@x.com")
    client.post("/logout")
    r = client.get("/documentos", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303


def test_raiz_redirige_a_documentos(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/documentos"


def test_login_get_muestra_formulario(client):
    r = client.get("/login")
    assert r.status_code == 200 and "<form" in r.text


def test_crear_admin(db):
    u = crear_admin(db, "root@x.com", "Root", "secreta123")
    assert u.es_admin and u.activo


def test_cli_main_crea_admin(app, db, monkeypatch):
    from app import cli
    from app.modelos import Usuario

    monkeypatch.setattr(cli, "getpass", lambda _="": "secreta123")
    entradas = iter(["Root", "root@x.com"])
    monkeypatch.setattr("builtins.input", lambda _="": next(entradas))
    codigo = cli.main(["app.cli", "crear-admin"], engine=app.state.engine)
    assert codigo == 0
    u = db.query(Usuario).filter_by(email="root@x.com").one()
    assert u.es_admin


def test_post_sin_sesion_desde_navegador_redirige_a_login(client):
    r = client.post("/documentos", headers={"Accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_put_sin_sesion_sigue_siendo_json_401(client):
    r = client.put("/documentos/1/contenido", json={"type": "doc", "content": []})
    assert r.status_code == 401 and r.json() == {"detalle": "no autenticado"}


def test_htmx_sin_sesion_sigue_siendo_json_401(client):
    r = client.post("/documentos", headers={"Accept": "text/html", "HX-Request": "true"})
    assert r.status_code == 401 and r.json() == {"detalle": "no autenticado"}
