"""Real PostgreSQL migration/deployment contracts; isolated schemas, never production data."""
import asyncio
import os
from uuid import uuid4
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

POSTGRES_URL=os.getenv('TEST_DATABASE_URL','')
postgres_only=pytest.mark.skipif(not POSTGRES_URL.startswith('postgresql'),reason='Requires dedicated PostgreSQL test database')

@pytest_asyncio.fixture
async def isolated_pg_schema():
    if not POSTGRES_URL.startswith('postgresql'): pytest.skip('PostgreSQL integration environment not configured')
    schema='traceform_verify_'+uuid4().hex
    admin=create_async_engine(POSTGRES_URL)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine=create_async_engine(POSTGRES_URL,connect_args={'server_settings':{'search_path':schema}})
    try: yield engine
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            # Identifier is a fixed prefix plus generated UUID, always owned by this fixture.
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()

@postgres_only
async def test_postgres_fresh_and_concurrent_migrations(isolated_pg_schema):
    from db.migrate import migrate
    engine=isolated_pg_schema
    await asyncio.gather(migrate(engine),migrate(engine))
    await migrate(engine)
    async with engine.connect() as connection:
        assert (await connection.execute(text('SELECT version_num FROM alembic_version'))).scalar_one()=='0009_measured_evaluations'
        assert (await connection.execute(text("SELECT count(*) FROM pg_enum e JOIN pg_type t ON e.enumtypid=t.oid JOIN pg_namespace n ON t.typnamespace=n.oid WHERE t.typname='generationstatus' AND e.enumlabel='CANCELLED' AND n.nspname=current_schema()"))).scalar_one()==1
        assert (await connection.execute(text('SELECT count(*) FROM creation_presets'))).scalar_one()==0

@postgres_only
async def test_postgres_legacy_upgrade_preserves_data_and_cancellation_enum(isolated_pg_schema):
    from alembic.config import Config
    from alembic import command
    from db.migrate import migrate
    engine=isolated_pg_schema
    cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    cfg.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'db/migrations'))
    async with engine.begin() as connection:
        def baseline(sync_connection):
            cfg.attributes['connection']=sync_connection
            command.upgrade(cfg,'0001_baseline')
        await connection.run_sync(baseline)
        sid,gid=uuid4(),uuid4()
        await connection.execute(text("INSERT INTO sources(id,extracted_text,sensitivity,sensitivity_source,sensitivity_confidence) VALUES (:id,'Synthetic preservation fixture','PUBLIC','OPERATOR',1)"),{'id':sid})
        await connection.execute(text("INSERT INTO generations(id,source_id,output_types,params,status,budget_type,budget_used,total_tokens,total_cost_usd,rerun_count) VALUES (:id,:source,'[\"executive_summary\"]','{}','QUEUED','tokens',0,0,0,0)"),{'id':gid,'source':sid})
        # Simulate an old installation that has data but no recorded Alembic baseline.
        await connection.execute(text('DELETE FROM alembic_version'))
    await migrate(engine)
    async with engine.begin() as connection:
        assert (await connection.execute(text('SELECT extracted_text FROM sources WHERE id=:id'),{'id':sid})).scalar_one()=='Synthetic preservation fixture'
        assert (await connection.execute(text('SELECT was_truncated FROM sources WHERE id=:id'),{'id':sid})).scalar_one() is False
        await connection.execute(text("UPDATE generations SET status='CANCELLED' WHERE id=:id"),{'id':gid})
        assert (await connection.execute(text('SELECT status::text FROM generations WHERE id=:id'),{'id':gid})).scalar_one()=='CANCELLED'

@postgres_only
async def test_production_requires_explicit_migration_and_accepts_current_schema(isolated_pg_schema,monkeypatch):
    from cryptography.fernet import Fernet
    from db.migrate import initialize,migrate
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('TRACEFORM_AUTO_MIGRATE','false')
    monkeypatch.setenv('API_KEYS','isolated-test-key');monkeypatch.setenv('TRACEFORM_MASTER_KEY',Fernet.generate_key().decode())
    with pytest.raises(RuntimeError,match='Run python -m db.migrate'):
        await initialize(isolated_pg_schema)
    await migrate(isolated_pg_schema)
    await initialize(isolated_pg_schema)

async def test_readiness_uses_database_without_provider_call(client):
    response=await client.get('/api/v1/healthz/ready')
    assert response.status_code==200 and response.json()=={'status':'ready','database':'ok'}

async def test_readiness_failure_hides_connection_details(client):
    from unittest.mock import AsyncMock
    from api.main import app
    from db.session import get_db
    previous=app.dependency_overrides[get_db]
    async def offline():
        yield type('Offline',(),{'execute':AsyncMock(side_effect=RuntimeError('postgresql://secret-password@private-host'))})()
    app.dependency_overrides[get_db]=offline
    try:
        response=await client.get('/api/v1/healthz/ready')
        assert response.status_code==503 and 'secret-password' not in response.text
    finally: app.dependency_overrides[get_db]=previous
