from app.config import Settings


def test_salud(client):
    r = client.get("/salud")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_database_url_de_prueba_usa_otra_base():
    s = Settings(mysql_user="u", mysql_password="p", mysql_database="prod",
                 mysql_test_database="editor_test", secret_key="x")
    assert s.database_url().endswith("/prod?charset=utf8mb4")
    assert s.database_url(test=True).endswith("/editor_test?charset=utf8mb4")
