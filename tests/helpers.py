from app.usuarios.servicio import crear_usuario


def crear(db, email, password="secreta123", es_admin=False):
    return crear_usuario(db, email, "Usuario de prueba", password, es_admin=es_admin)


def entrar(client, email, password="secreta123"):
    r = client.post("/login", data={"email": email, "password": password}, follow_redirects=False)
    assert r.status_code == 303
