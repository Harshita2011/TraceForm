"""Run independently of the API: python -m orchestrator.worker [--once]."""
import argparse
import asyncio
import logging
import os
from dotenv import load_dotenv


async def healthcheck():
    import socket
    from sqlalchemy import select
    from db.session import AsyncSessionLocal, engine
    from db.models import WorkerState
    from orchestrator.runtime import utcnow, aware
    try:
        async with AsyncSessionLocal() as db:
            last_seen = (await db.execute(select(WorkerState.last_seen_at).where(
                WorkerState.worker_id.startswith(socket.gethostname() + ":")
            ).order_by(WorkerState.last_seen_at.desc()).limit(1))).scalar_one_or_none()
            return bool(last_seen and (utcnow() - aware(last_seen)).total_seconds() < 30)
    except Exception:
        return False
    finally:
        await engine.dispose()


async def main(once=False):
    from db.session import engine
    from db.migrate import initialize
    from orchestrator.queue import run_once, run_forever
    await initialize(engine)
    try:
        if once:
            await run_once()
        else:
            await run_forever(worker_id=os.getenv("TRACEFORM_WORKER_ID"))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    if args.healthcheck:
        raise SystemExit(0 if asyncio.run(healthcheck()) else 1)
    try:
        asyncio.run(main(args.once))
    except KeyboardInterrupt:
        pass
