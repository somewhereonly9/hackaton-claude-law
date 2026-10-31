import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base
from app.main import create_app


@pytest.fixture
def app():
    aplicacion = create_app(test=True)
    Base.metadata.drop_all(aplicacion.state.engine)
    Base.metadata.create_all(aplicacion.state.engine)
    yield aplicacion
    aplicacion.state.engine.dispose()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db(app):
    s = Session(app.state.engine)
    yield s
    s.close()
