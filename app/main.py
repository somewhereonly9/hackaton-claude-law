from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, get_settings
from app.db import crear_engine


def create_app(settings: Settings | None = None, test: bool = False) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI()
    app.state.settings = settings
    app.state.engine = crear_engine(settings.database_url(test=test))
    app.state.SessionLocal = sessionmaker(bind=app.state.engine, expire_on_commit=False)

    app.mount(
        "/estaticos",
        StaticFiles(directory=Path(__file__).parent / "web" / "estaticos"),
        name="estaticos",
    )
    app.add_middleware(
        SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False
    )

    @app.get("/salud")
    def salud():
        return {"ok": True}

    return app


app = create_app()
