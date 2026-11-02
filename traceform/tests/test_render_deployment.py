"""Hosted startup contracts without external services or provider requests."""
import asyncio
from datetime import timedelta
import ssl
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from db.connection import connection_settings
from deployment import render


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_neon_url_uses_async_driver_and_verified_tls(scheme):
    url, args = connection_settings(
        f"{scheme}://owner:p%40ss%2Fword@ep-example.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
    assert url.drivername == "postgresql+asyncpg"
    assert url.password == "p@ss/word"
    assert not url.query
    assert args["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert args["ssl"].check_hostname


def test_neon_cannot_disable_tls():
    with pytest.raises(ValueError, match="TLS"):
        connection_settings("postgresql://u:p@ep-example.neon.tech/db?sslmode=disable")


def test_local_postgres_and_sqlite_remain_compatible():
    url, args = connection_settings("postgresql+asyncpg://u:p@localhost/db")
    assert not args and not url.query
    _, args = connection_settings("sqlite+aiosqlite:///./test.db")
    assert args == {"check_same_thread": False, "timeout": 30}


async def test_migrations_accept_url_encoded_password(monkeypatch, tmp_path):
    from db.migrate import migrate
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    # The injected isolated connection prevents any network request. Alembic must
    # still parse the configured Neon URL without treating %40 as interpolation.
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p%40ss%2Fword@ep-test.neon.tech/db?sslmode=require")
    engine = create_async_engine("sqlite+aiosqlite:///" + (tmp_path / "migration.db").as_posix())
    try:
        await migrate(engine)
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() == "0009_measured_evaluations"
    finally:
        await engine.dispose()


@pytest.fixture
def hosted_config(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@ep-test.neon.tech/db?sslmode=require")
    monkeypatch.setenv("TRACEFORM_MASTER_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("API_KEYS", "a" * 48 + ":installation:admin")
    monkeypatch.setenv("TRACEFORM_WEB_ORIGINS", "https://example.vercel.app")
    monkeypatch.setenv("PORT", "10042")
    # configure changes these; restore them after the test.
    for name in ("APP_ENV", "TRACEFORM_AUTO_MIGRATE", "OBJECT_STORAGE_PATH", "PYTHONUNBUFFERED"):
        monkeypatch.setenv(name, "test")


def test_hosted_config_uses_explicit_production_storage(hosted_config):
    import os
    assert render.configure() == 10042
    assert os.environ["APP_ENV"] == "production"
    assert os.environ["TRACEFORM_AUTO_MIGRATE"] == "false"
    assert os.environ["OBJECT_STORAGE_PATH"] == "/var/data/traceform"


@pytest.mark.parametrize("name,value", [
    ("DATABASE_URL", "sqlite+aiosqlite:///accidental.db"),
    ("DATABASE_URL", "postgresql://u:p@ep-test-pooler.aws.neon.tech/db"),
    ("TRACEFORM_MASTER_KEY", ""), ("API_KEYS", "short-key"),
    ("TRACEFORM_WEB_ORIGINS", "https://example.vercel.app/"),
    ("TRACEFORM_WEB_ORIGINS", "http://localhost:3000"), ("PORT", "0"),
])
def test_invalid_hosted_config_fails_before_start(hosted_config, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        render.configure()


@pytest.mark.parametrize("migration_code,expected_children", [(1, 1), (0, 3)])
async def test_migrate_first_and_stop_sibling_on_failure(monkeypatch, migration_code, expected_children):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler", lambda *args: None)
    monkeypatch.setattr(loop, "remove_signal_handler", lambda *args: None)
    spawned = []
    class Child:
        def __init__(self, code):
            self.pid = 100 + len(spawned)
            self.returncode = None
            self.code = code
        async def wait(self):
            if self.code is None:
                await asyncio.Event().wait()
            self.returncode = self.code
            return self.code
    async def spawn(*args, **kwargs):
        index = len(spawned)
        child = Child(migration_code if index == 0 else None if index == 1 else 0)
        spawned.append((args, kwargs, child))
        return child
    monkeypatch.setattr(render.asyncio, "create_subprocess_exec", spawn)
    stop = AsyncMock()
    monkeypatch.setattr(render, "stop_process", stop)
    assert await render.supervise(10000) == 1
    assert len(spawned) == expected_children
    assert spawned[0][0][-2:] == ("-m", "db.migrate")
    assert stop.await_count == expected_children
    if migration_code == 0:
        assert spawned[1][0][-1] == "orchestrator.worker"
        prefix = spawned[2][1]["env"]["TRACEFORM_REQUIRED_WORKER_PREFIX"]
        assert prefix == spawned[1][1]["env"]["TRACEFORM_WORKER_ID"]
        assert ":render:" in prefix


async def test_hosted_health_rejects_stale_and_other_worker(client, db_session, monkeypatch):
    from db.models import WorkerState
    from orchestrator.runtime import utcnow
    monkeypatch.setenv("TRACEFORM_REQUIRED_WORKER_PREFIX", "this-host:42:")
    db_session.add(WorkerState(worker_id="other-host:42:abc", last_seen_at=utcnow()))
    current = WorkerState(worker_id="this-host:42:abc", last_seen_at=utcnow() - timedelta(seconds=90))
    db_session.add(current)
    await db_session.flush()
    assert (await client.get("/api/v1/healthz/service")).status_code == 503
    current.last_seen_at = utcnow()
    await db_session.flush()
    response = await client.get("/api/v1/healthz/service")
    assert response.status_code == 200
    assert response.json()["storage"] == "ok"


async def test_hosted_health_checks_storage(client, db_session, monkeypatch, tmp_path):
    from db.models import WorkerState
    from orchestrator.runtime import utcnow
    monkeypatch.setenv("TRACEFORM_REQUIRED_WORKER_PREFIX", "host:7:")
    monkeypatch.setenv("OBJECT_STORAGE_PATH", str(tmp_path / "missing-storage"))
    db_session.add(WorkerState(worker_id="host:7:abc", last_seen_at=utcnow()))
    await db_session.flush()
    response = await client.get("/api/v1/healthz/service")
    assert response.status_code == 503 and str(tmp_path) not in response.text
