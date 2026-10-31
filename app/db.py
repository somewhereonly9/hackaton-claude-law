from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def crear_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_db(request: Request) -> Iterator[Session]:
    s = request.app.state.SessionLocal()
    try:
        yield s
    finally:
        s.close()
