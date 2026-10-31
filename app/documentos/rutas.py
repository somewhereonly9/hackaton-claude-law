import json

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from markupsafe import escape
from sqlalchemy.orm import Session

from app.auth.dependencias import usuario_actual
from app.db import get_db
from app.documentos import servicio
from app.modelos import Usuario
from app.web.render import templates

router = APIRouter(prefix="/documentos")

TAMANO_MAXIMO = 2_097_152


@router.get("")
def listar(request: Request, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "documentos.html",
        {"usuario": usuario, "documentos": servicio.listar(db, usuario.id)},
    )


@router.post("")
def crear(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    documento = servicio.crear(db, usuario.id)
    return RedirectResponse(f"/documentos/{documento.id}", status_code=303)


# Provisional: la Task 7 reemplaza esta respuesta por la página del editor.
@router.get("/{documento_id}")
def abrir(documento_id: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    documento = servicio.obtener(db, usuario.id, documento_id)
    return HTMLResponse(f"<h1>{escape(documento.titulo)}</h1>")


@router.put("/{documento_id}/contenido")
async def guardar_contenido(
    documento_id: int,
    request: Request,
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    if int(request.headers.get("content-length", 0)) > TAMANO_MAXIMO:
        return JSONResponse({"detalle": "El documento es demasiado grande."}, status_code=413)
    try:
        contenido = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"detalle": "JSON inválido."}, status_code=422)
    documento = servicio.guardar_contenido(db, usuario.id, documento_id, contenido)
    return {"ok": True, "actualizado_en": documento.actualizado_en.isoformat()}


@router.post("/{documento_id}/titulo")
def renombrar(
    documento_id: int,
    titulo: str = Form(""),
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    documento = servicio.renombrar(db, usuario.id, documento_id, titulo)
    return HTMLResponse(f'<span class="titulo-documento">{escape(documento.titulo)}</span>')


@router.delete("/{documento_id}")
def borrar(documento_id: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    servicio.borrar(db, usuario.id, documento_id)
    return Response(status_code=200)
