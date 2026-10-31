from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Documento

CONTENIDO_VACIO = {"type": "doc", "content": []}
TITULO_POR_DEFECTO = "Documento sin título"
TITULO_MAXIMO = 200


class NoEncontrado(Exception):
    pass


class ContenidoInvalido(Exception):
    pass


def _validar_titulo(titulo: str) -> str:
    titulo = titulo.strip()
    if not titulo or len(titulo) > TITULO_MAXIMO:
        raise ContenidoInvalido(f"El título debe tener de 1 a {TITULO_MAXIMO} caracteres.")
    return titulo


def crear(db: Session, usuario_id: int, titulo: str | None = None) -> Documento:
    titulo = TITULO_POR_DEFECTO if titulo is None else _validar_titulo(titulo)
    documento = Documento(usuario_id=usuario_id, titulo=titulo, contenido=dict(CONTENIDO_VACIO))
    db.add(documento)
    db.commit()
    return documento


def listar(db: Session, usuario_id: int) -> list[Documento]:
    consulta = (
        select(Documento)
        .where(Documento.usuario_id == usuario_id)
        .order_by(Documento.actualizado_en.desc(), Documento.id.desc())
    )
    return list(db.scalars(consulta))


def obtener(db: Session, usuario_id: int, documento_id: int) -> Documento:
    documento = db.scalar(
        select(Documento).where(Documento.id == documento_id, Documento.usuario_id == usuario_id)
    )
    if documento is None:
        raise NoEncontrado()
    return documento


def renombrar(db: Session, usuario_id: int, documento_id: int, titulo: str) -> Documento:
    documento = obtener(db, usuario_id, documento_id)
    documento.titulo = _validar_titulo(titulo)
    db.commit()
    db.refresh(documento)
    return documento


def guardar_contenido(db: Session, usuario_id: int, documento_id: int, contenido: dict) -> Documento:
    documento = obtener(db, usuario_id, documento_id)
    if not isinstance(contenido, dict) or contenido.get("type") != "doc":
        raise ContenidoInvalido("El contenido debe ser un documento con raíz \"doc\".")
    documento.contenido = contenido
    db.commit()
    db.refresh(documento)
    return documento


def borrar(db: Session, usuario_id: int, documento_id: int) -> None:
    db.delete(obtener(db, usuario_id, documento_id))
    db.commit()
