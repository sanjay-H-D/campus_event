"""SQLAlchemy engine, declarative base, and request-scoped sessions."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import DATABASE_URL

database_url = make_url(DATABASE_URL)
if database_url.drivername in {"postgres", "postgresql"}:
    database_url = database_url.set(drivername="postgresql+psycopg")

engine_options = {}
if database_url.get_backend_name() == "sqlite":
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
