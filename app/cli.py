import sys
from getpass import getpass

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import crear_engine
from app.modelos import Usuario
from app.usuarios.servicio import ContrasenaInvalida, EmailDuplicado, crear_usuario


def crear_admin(db: Session, email: str, nombre: str, password: str) -> Usuario:
    return crear_usuario(db, email, nombre, password, es_admin=True)


def main(argv: list[str], engine: Engine | None = None) -> int:
    if len(argv) != 2 or argv[1] != "crear-admin":
        print("Uso: python -m app.cli crear-admin")
        return 2
    nombre = input("Nombre: ")
    email = input("Correo: ")
    password = getpass("Contraseña: ")
    if password != getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden")
        return 1
    engine = engine or crear_engine(get_settings().database_url())
    with Session(engine) as db:
        try:
            usuario = crear_admin(db, email, nombre, password)
        except (EmailDuplicado, ContrasenaInvalida) as e:
            print(f"No se pudo crear el administrador: {e}")
            return 1
        print(f"Administrador creado: {usuario.email}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
