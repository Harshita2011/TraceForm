"""
# Test configuration — async pytest setup with file-based SQLite test DB.
# Real Postgres is used if TEST_DATABASE_URL env var is set.
"""

import os
import tempfile
import uuid as _uuid
from pathlib import Path
from typing import AsyncGenerator

# Set test environment variables before any app imports
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("API_KEYS", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-placeholder")
# The backend loads .env during import. Never let that import pick up a developer's live Gemini key.
os.environ['GEMINI_API_KEY'] = ''
os.environ.setdefault("ANTHROPIC_MODEL", "claude-opus-4-5")
os.environ.setdefault("OBJECT_STORAGE_PATH", str(Path(tempfile.gettempdir()) / "traceform_test_storage"))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# §4 / Phase 2 — Celery tasks run synchronously in tests (no real broker needed).
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")

import pytest
import pytest_asyncio
import socket
import ipaddress
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.main import app
from api.dependencies import get_db
from db.models import Base

# External DB (real Postgres) if TEST_DATABASE_URL is set; otherwise file-based SQLite.
_EXTERNAL_DB_URL = os.getenv("TEST_DATABASE_URL", None)


@pytest.fixture(autouse=True)
def no_external_provider_network(monkeypatch):
    """Tests may reach loopback HTTP fixtures and their explicit test DB, never a paid provider."""
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex
    database_addresses = set()
    database_port = None
    if _EXTERNAL_DB_URL:
        from sqlalchemy.engine import make_url
        parsed = make_url(_EXTERNAL_DB_URL)
        database_port = parsed.port or 5432
        database_addresses = {address[4][0] for address in socket.getaddrinfo(parsed.host, database_port)}
    def permitted(address):
        if not isinstance(address, tuple): return True  # Local Unix-domain sockets.
        host, port = address[:2]
        try: loopback = ipaddress.ip_address(host).is_loopback
        except ValueError: loopback = host == 'localhost'
        return loopback or host in database_addresses and port == database_port
    def connect(sock, address):
        if not permitted(address): raise RuntimeError('External provider network access is disabled in tests; use a local mock.')
        return original(sock, address)
    def connect_ex(sock, address):
        if not permitted(address): raise RuntimeError('External provider network access is disabled in tests; use a local mock.')
        return original_ex(sock, address)
    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', connect_ex)


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """
    Create a fresh async engine for each test function.
    Uses a unique per-test temp file on disk (not :memory:) so that sessions opened
    by _finalize_generation (via patched AsyncSessionLocal) can see committed data.
    """
    if _EXTERNAL_DB_URL:
        from sqlalchemy.engine import make_url
        database_name = make_url(_EXTERNAL_DB_URL).database or ""
        if not database_name.startswith("traceform_test_") or os.getenv("TRACEFORM_RESET_TEST_DATABASE") != "1":
            raise RuntimeError("External tests reset tables: use a dedicated traceform_test_* database and set TRACEFORM_RESET_TEST_DATABASE=1.")
        db_url = _EXTERNAL_DB_URL
        tmp_path = None
        engine = create_async_engine(db_url, echo=False)
    else:
        # Unique per-test file — isolated between tests, visible across connections
        tmp_path = Path(tempfile.gettempdir()) / f"traceform_test_{_uuid.uuid4().hex}.db"
        db_url = f"sqlite+aiosqlite:///{tmp_path}"
        engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

    if tmp_path and tmp_path.exists():
        try:
            tmp_path.unlink()
        except Exception:
            pass


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async DB session for each test."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
def session_factory(test_engine):
    """
    Expose the async_sessionmaker bound to the test engine.
    Used by tests that patch orchestrator.jobs.AsyncSessionLocal to run against the test DB.
    Since we use a file-based SQLite, multiple connections from this factory see the same data.
    """
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB override injected."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async def available_provider(configuration=None):
        return {"available": True, "model": "test-model", "message": "Ready"}
    monkeypatch.setattr("agents.availability.provider_health", available_provider)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": "test-key"},
    ) as c:
        yield c

    app.dependency_overrides.clear()
