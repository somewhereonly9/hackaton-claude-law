from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencias import admin_actual
from app.db import get_db
from app.modelos import Usuario
from app.usuarios import servicio
from app.web.render import templates

router = APIRouter(prefix="/admin/usuarios")


def _pagina(request: Request, db: Session, admin: Usuario, error: str | None = None, codigo: int = 200):
    return templates.TemplateResponse(
        request,
        "admin_usuarios.html",
        {"usuario": admin, "usuarios": servicio.listar_usuarios(db), "error": error},
        status_code=codigo,
    )


def _redireccion():
    return RedirectResponse("/admin/usuarios", status_code=303)


@router.get("")
def listar(request: Request, admin: Usuario = Depends(admin_actual), db: Session = Depends(get_db)):
    return _pagina(request, db, admin)


@router.post("")
def crear(
    request: Request,
    email: str = Form(""),
    nombre: str = Form(""),
    password: str = Form(""),
    es_admin: str | None = Form(None),
    admin: Usuario = Depends(admin_actual),
    db: Session = Depends(get_db),
):
    try:
        servicio.crear_usuario(db, email, nombre, password, es_admin=es_admin == "true")
    except servicio.EmailDuplicado:
        return _pagina(request, db, admin, "Error: ya existe un usuario con ese correo.", 400)
    except (servicio.ContrasenaInvalida, servicio.DatosInvalidos) as e:
        return _pagina(request, db, admin, str(e), 400)
    return _redireccion()


@router.post("/{usuario_id}/contrasena")
def restablecer_contrasena(
    request: Request,
    usuario_id: int,
    password: str = Form(""),
    admin: Usuario = Depends(admin_actual),
    db: Session = Depends(get_db),
):
    try:
        servicio.cambiar_contrasena(db, usuario_id, password)
    except servicio.UsuarioNoEncontrado:
        raise HTTPException(status_code=404) from None
    except servicio.ContrasenaInvalida as e:
        return _pagina(request, db, admin, str(e), 400)
    return _redireccion()


@router.post("/{usuario_id}/activo")
def cambiar_activo(
    request: Request,
    usuario_id: int,
    activo: str = Form(""),
    admin: Usuario = Depends(admin_actual),
    db: Session = Depends(get_db),
):
    if activo not in ("true", "false"):
        return _pagina(request, db, admin, "Valor de estado no válido.", 400)
    try:
        servicio.cambiar_activo(db, admin, usuario_id, activo == "true")
    except servicio.UsuarioNoEncontrado:
        raise HTTPException(status_code=404) from None
    except servicio.AccionNoPermitida as e:
        return _pagina(request, db, admin, str(e), 400)
    return _redireccion()
