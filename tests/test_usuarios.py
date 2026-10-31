import pytest

from app.auth.contrasenas import hashear, verificar
from app.usuarios.servicio import (
    AccionNoPermitida,
    ContrasenaInvalida,
    EmailDuplicado,
    autenticar,
    cambiar_activo,
    cambiar_contrasena,
    crear_usuario,
)


def test_hash_no_es_la_contrasena_y_verifica():
    h = hashear("secreta123")
    assert h != "secreta123" and h.startswith("$argon2")
    assert verificar(h, "secreta123") and not verificar(h, "otra12345")


def test_email_se_normaliza(db):
    crear_usuario(db, " Ana@Ejemplo.COM ", "Ana", "secreta123")
    assert autenticar(db, "ana@ejemplo.com", "secreta123") is not None
    with pytest.raises(EmailDuplicado):
        crear_usuario(db, "ANA@ejemplo.com", "Otra", "secreta123")


def test_contrasena_corta_se_rechaza(db):
    with pytest.raises(ContrasenaInvalida):
        crear_usuario(db, "b@x.com", "B", "corta")


def test_usuario_inactivo_no_autentica(db):
    admin = crear_usuario(db, "admin@x.com", "Admin", "secreta123", es_admin=True)
    u = crear_usuario(db, "c@x.com", "C", "secreta123")
    cambiar_activo(db, admin, u.id, False)
    assert autenticar(db, "c@x.com", "secreta123") is None


def test_admin_no_puede_desactivarse(db):
    admin = crear_usuario(db, "admin@x.com", "Admin", "secreta123", es_admin=True)
    with pytest.raises(AccionNoPermitida):
        cambiar_activo(db, admin, admin.id, False)


def test_cambiar_contrasena(db):
    u = crear_usuario(db, "d@x.com", "D", "secreta123")
    cambiar_contrasena(db, u.id, "nueva12345")
    assert autenticar(db, "d@x.com", "nueva12345") is not None
    assert autenticar(db, "d@x.com", "secreta123") is None
