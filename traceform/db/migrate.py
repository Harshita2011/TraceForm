"""Versioned, non-destructive migration runner for existing and new installations."""
from pathlib import Path
from alembic.config import Config
from alembic import command


async def migrate(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    async with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            from sqlalchemy import text
            await connection.execute(text("SELECT pg_advisory_xact_lock(20483002)"))
        def upgrade(sync_connection):
            config.attributes["connection"] = sync_connection
            command.upgrade(config, "head")
        await connection.run_sync(upgrade)


async def initialize(engine):
    """Production deployments migrate explicitly before starting API and workers."""
    import os
    from sqlalchemy import text
    production = os.getenv("APP_ENV") == "production"
    if production and (not os.getenv("TRACEFORM_MASTER_KEY") or not os.getenv("API_KEYS")):
        raise RuntimeError("Production requires TRACEFORM_MASTER_KEY and API_KEYS.")
    if os.getenv("TRACEFORM_AUTO_MIGRATE", "false" if production else "true").lower() == "true":
        await migrate(engine)
    else:
        from alembic.script import ScriptDirectory
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        head = ScriptDirectory.from_config(config).get_current_head()
        async with engine.connect() as connection:
            try:
                current = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
            except Exception as exc:
                raise RuntimeError("Run python -m db.migrate before starting this service.") from exc
            if current != head:
                raise RuntimeError("Database is behind; run python -m db.migrate before starting this service.")


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    from db.session import engine
    async def main():
        try:
            await migrate(engine)
        finally:
            await engine.dispose()
    asyncio.run(main())
