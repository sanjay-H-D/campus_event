from unittest.mock import patch

import pytest

from backend.database import initialization


def test_initialize_database_uses_sqlite_initializer():
    with (
        patch.object(initialization.engine.dialect, "name", "sqlite"),
        patch.object(initialization, "initialize_sqlite_database") as initialize_sqlite,
    ):
        initialization.initialize_database()

    initialize_sqlite.assert_called_once_with()


def test_initialize_database_skips_initializers_for_postgresql():
    with (
        patch.object(initialization.engine.dialect, "name", "postgresql"),
        patch.object(initialization, "initialize_sqlite_database") as initialize_sqlite,
        patch.object(initialization, "initialize_postgresql_database") as initialize_postgresql,
    ):
        initialization.initialize_database()

    initialize_sqlite.assert_not_called()
    initialize_postgresql.assert_not_called()


def test_initialize_database_rejects_unsupported_dialect():
    with patch.object(initialization.engine.dialect, "name", "mysql"):
        with pytest.raises(RuntimeError, match="Unsupported database dialect: mysql"):
            initialization.initialize_database()


def test_initialize_postgresql_database_rejects_sqlite_without_creating_schema():
    with (
        patch.object(initialization.engine.dialect, "name", "sqlite"),
        patch.object(initialization.Base.metadata, "create_all") as create_all,
    ):
        with pytest.raises(RuntimeError, match="requires a PostgreSQL engine"):
            initialization.initialize_postgresql_database()

    create_all.assert_not_called()


def test_initialize_postgresql_database_creates_schema_for_postgresql():
    with (
        patch.object(initialization.engine.dialect, "name", "postgresql"),
        patch.object(initialization.Base.metadata, "create_all") as create_all,
    ):
        initialization.initialize_postgresql_database()

    create_all.assert_called_once_with(bind=initialization.engine)
