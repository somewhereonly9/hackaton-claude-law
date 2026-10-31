from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

import app.modelos  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import Settings, get_settings
from app.admin import rutas as rutas_admin
from app.auth import rutas as rutas_auth
from app.auth.dependencias import NoAutenticado, manejar_no_autenticado
from app.db import crear_engine
from app.documentos import rutas as rutas_documentos
from app.documentos.servicio import ContenidoInvalido, NoEncontrado


def create_app(settings: Settings | None = None, test: bool = False) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI()
    app.state.settings = settings
    app.state.engine = crear_engine(settings.database_url(test=test))
    # expire_on_commit=False: las pruebas escriben con una sesión y leen con otra.
    app.state.SessionLocal = sessionmaker(bind=app.state.engine, expire_on_commit=False)

    app.mount(
        "/estaticos",
        StaticFiles(directory=Path(__file__).parent / "web" / "estaticos"),
        name="estaticos",
    )
    app.add_middleware(
        SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False
    )

    app.add_exception_handler(NoAutenticado, manejar_no_autenticado)
    async def no_encontrado(request: Request, exc: NoEncontrado):
        return JSONResponse({"detalle": "no encontrado"}, status_code=404)

    async def contenido_invalido(request: Request, exc: ContenidoInvalido):
        return JSONResponse({"detalle": str(exc)}, status_code=422)

    app.add_exception_handler(NoEncontrado, no_encontrado)
    app.add_exception_handler(ContenidoInvalido, contenido_invalido)
    app.include_router(rutas_auth.router)
    app.include_router(rutas_documentos.router)
    app.include_router(rutas_admin.router)

    @app.get("/salud")
    def salud():
        return {"ok": True}

    return app


app = create_app()
