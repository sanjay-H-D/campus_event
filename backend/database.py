"""Database setup for the Campus Event Ticketing Engine."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# The v2 schema is kept in a new file so an older single-college database is
# preserved instead of being silently altered or losing existing bookings.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./campus_event_engine.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
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
