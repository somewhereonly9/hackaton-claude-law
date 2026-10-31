from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.modelos import Usuario


class NoAutenticado(Exception):
    pass


def manejar_no_autenticado(request: Request, exc: NoAutenticado):
    if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/login", status_code=303)
    return JSONResponse({"detalle": "no autenticado"}, status_code=401)


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        raise NoAutenticado()
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        request.session.clear()
        raise NoAutenticado()
    return usuario


def admin_actual(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    if not usuario.es_admin:
        raise HTTPException(status_code=404)
    return usuario
