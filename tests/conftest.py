"""
Shared test fixtures for the Video Creator Platform test suite.
Uses SQLite in-memory for DB tests and mocks for MinIO.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta

# Ensure project root is on PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Also add admin-api to path for imports
ADMIN_API_DIR = os.path.join(ROOT_DIR, "admin-api")
if ADMIN_API_DIR not in sys.path:
    sys.path.insert(0, ADMIN_API_DIR)

# ── Override database config BEFORE any imports ──────────────────────────────

# Use SQLite in-memory for testing
os.environ["DATABASE_URL"] = "sqlite:///test_video_creator.db"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared_core.database import Base, get_db
from shared_core import models

# ── Test DB Engine ────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Enable foreign keys for SQLite
@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables before each test, drop after."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a test DB session that rolls back after each test."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── FastAPI Test Client ──────────────────────────────────────────────────────

@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden DB dependency."""
    # Lazily import to avoid circular issues
    from admin_api_app import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user directly in the DB."""
    from auth import get_password_hash

    user = models.User(
        email="test@example.com",
        password_hash=get_password_hash("testpass123"),
        role="creator",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """Return Authorization headers for the test user."""
    from auth import create_access_token

    token = create_access_token(data={"sub": test_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def authenticated_client(client, auth_headers):
    """A TestClient wrapper that automatically adds auth headers."""
    class AuthClient:
        def __init__(self, client, headers):
            self._client = client
            self._headers = headers

        def get(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.get(url, **kwargs)

        def post(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.post(url, **kwargs)

        def delete(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.delete(url, **kwargs)

        def put(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.put(url, **kwargs)

        def patch(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(self._headers)
            return self._client.patch(url, **kwargs)

    return AuthClient(client, auth_headers)


@pytest.fixture
def test_project(db_session, test_user):
    """Create a test project."""
    project = models.Project(
        name="Test Project",
        description="Test description",
        user_id=test_user.id,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project
