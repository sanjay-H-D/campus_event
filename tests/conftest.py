import os

os.environ["SECRET_KEY"] = "test-secret-key-that-is-only-used-by-pytest"
os.environ["DATABASE_URL"] = "sqlite:///./test_campus_event_engine.db"

import pytest
from fastapi.testclient import TestClient

from backend.database import Base, engine
from backend.main import app


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
