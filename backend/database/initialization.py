"""Database schema initialization and backward-compatible migrations."""

from sqlalchemy import inspect, text

from .models import Base
from .session import engine


def initialize_database() -> None:
    """Create missing tables and apply additive migrations for existing databases."""
    Base.metadata.create_all(bind=engine)
    migrations = {
        "events": ("duration", "VARCHAR(60) NOT NULL DEFAULT '1 hour'"),
        "bookings": ("reservation_expires_at", "DATETIME"),
    }
    with engine.begin() as connection:
        for table, (column, definition) in migrations.items():
            if column not in {item["name"] for item in inspect(engine).get_columns(table)}:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
