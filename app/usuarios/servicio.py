from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.contrasenas import hashear, verificar
from app.modelos import Usuario

LONGITUD_MINIMA = 8
EMAIL_MAXIMO = 255
NOMBRE_MAXIMO = 200


class EmailDuplicado(Exception):
    pass


class DatosInvalidos(Exception):
    pass


class ContrasenaInvalida(Exception):
    pass


class AccionNoPermitida(Exception):
    pass


class UsuarioNoEncontrado(Exception):
    pass


def _normalizar(email: str) -> str:
    return email.strip().lower()


def _validar_contrasena(password: str) -> None:
    if len(password) < LONGITUD_MINIMA:
        raise ContrasenaInvalida(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres."
        )


def _obtener(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNoEncontrado(usuario_id)
    return usuario


def crear_usuario(
    db: Session, email: str, nombre: str, password: str, es_admin: bool = False
) -> Usuario:
    email = _normalizar(email)
    nombre = nombre.strip()
    if not email or "@" not in email or len(email) > EMAIL_MAXIMO:
        raise DatosInvalidos(f"Escribe un correo válido de hasta {EMAIL_MAXIMO} caracteres.")
    if not nombre or len(nombre) > NOMBRE_MAXIMO:
        raise DatosInvalidos(f"El nombre debe tener de 1 a {NOMBRE_MAXIMO} caracteres.")
    _validar_contrasena(password)
    usuario = Usuario(
        email=email,
        nombre=nombre,
        password_hash=hashear(password),
        es_admin=es_admin,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailDuplicado(usuario.email) from None
    return usuario


def autenticar(db: Session, email: str, password: str) -> Usuario | None:
    usuario = db.scalar(select(Usuario).where(Usuario.email == _normalizar(email)))
    if usuario is None or not usuario.activo:
        return None
    if not verificar(usuario.password_hash, password):
        return None
    return usuario


def cambiar_contrasena(db: Session, usuario_id: int, password: str) -> None:
    _validar_contrasena(password)
    usuario = _obtener(db, usuario_id)
    usuario.password_hash = hashear(password)
    db.commit()


def cambiar_activo(db: Session, actor: Usuario, usuario_id: int, activo: bool) -> Usuario:
    if actor.id == usuario_id:
        raise AccionNoPermitida("Un administrador no puede desactivarse a sí mismo.")
    usuario = _obtener(db, usuario_id)
    usuario.activo = activo
    db.commit()
    return usuario


def listar_usuarios(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).order_by(Usuario.email)))
