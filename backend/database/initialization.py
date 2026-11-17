"""Database schema initialization and backward-compatible migrations."""

from sqlalchemy import inspect, text

from .models import Base
from .session import engine


def initialize_database() -> None:
    """Create missing tables and apply additive migrations for existing databases."""
    migrate_legacy_payment_table()
    Base.metadata.create_all(bind=engine)
    migrations = {
        "events": ("duration", "VARCHAR(60) NOT NULL DEFAULT '1 hour'"),
        "bookings": ("reservation_expires_at", "DATETIME"),
    }
    with engine.begin() as connection:
        for table, (column, definition) in migrations.items():
            if column not in {item["name"] for item in inspect(engine).get_columns(table)}:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def migrate_legacy_payment_table() -> None:
    """Replace the old gateway-shaped payment table while preserving its rows."""
    inspector = inspect(engine)
    if "payments" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("payments")}
    if "payment_reference" in columns:
        return
    if "gateway_order_id" not in columns or "gateway_payment_id" not in columns:
        raise RuntimeError("The payments table has an unsupported schema and cannot be migrated safely.")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text(
            """
            CREATE TABLE payments_demo (
                id INTEGER NOT NULL PRIMARY KEY,
                booking_id INTEGER NOT NULL REFERENCES bookings(id),
                student_id INTEGER NOT NULL REFERENCES students(id),
                event_id INTEGER NOT NULL REFERENCES events(id),
                amount FLOAT NOT NULL,
                currency VARCHAR(3) NOT NULL,
                payment_reference VARCHAR(100) NOT NULL UNIQUE,
                payment_method VARCHAR(40) NOT NULL DEFAULT 'Demo Payment',
                payment_status VARCHAR(20) NOT NULL DEFAULT 'Pending',
                transaction_date DATETIME,
                created_at DATETIME NOT NULL
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO payments_demo
                (id, booking_id, student_id, event_id, amount, currency,
                 payment_reference, payment_method, payment_status,
                 transaction_date, created_at)
            SELECT id, booking_id, student_id, event_id, amount, currency,
                   COALESCE(gateway_payment_id, gateway_order_id, 'LEGACY-' || id),
                   COALESCE(payment_method, 'Demo Payment'),
                   payment_status, transaction_date, created_at
            FROM payments
            """
        ))
        connection.execute(text("DROP TABLE payments"))
        connection.execute(text("ALTER TABLE payments_demo RENAME TO payments"))
        connection.execute(text("CREATE INDEX ix_payments_payment_reference ON payments(payment_reference)"))
        connection.execute(text("CREATE INDEX ix_payments_booking_id ON payments(booking_id)"))
        connection.execute(text("CREATE INDEX ix_payments_student_id ON payments(student_id)"))
        connection.execute(text("CREATE INDEX ix_payments_event_id ON payments(event_id)"))
        connection.execute(text("CREATE INDEX ix_payments_payment_status ON payments(payment_status)"))
        connection.execute(text("PRAGMA foreign_keys=ON"))
