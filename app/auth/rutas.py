from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.usuarios.servicio import autenticar
from app.web.plantillas import templates

router = APIRouter()


@router.get("/")
def raiz():
    return RedirectResponse("/documentos", status_code=303)


@router.get("/login")
def formulario_login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"usuario": None, "error": None})


@router.post("/login")
def iniciar_sesion(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    usuario = autenticar(db, email, password)
    if usuario is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"usuario": None, "error": "Correo o contraseña incorrectos", "email": email},
            status_code=400,
        )
    request.session.clear()
    request.session["usuario_id"] = usuario.id
    return RedirectResponse("/documentos", status_code=303)


@router.post("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
