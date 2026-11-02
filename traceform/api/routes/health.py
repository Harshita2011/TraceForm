"""GET /api/v1/healthz — liveness check."""

import asyncio
from fastapi import APIRouter, HTTPException
from api.dependencies import CurrentOperator, DbSession

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz():
    """§3.11 — Liveness check. Returns 200 when the API process is up."""
    return {"status": "ok", "service": "traceform"}


@router.get("/healthz/ready")
async def ready(db: DbSession):
    from sqlalchemy import text
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2)
    except Exception:
        raise HTTPException(status_code=503, detail="Database is unavailable.")
    return {"status": "ready", "database": "ok"}


@router.get("/healthz/provider")
async def get_provider_health(operator: CurrentOperator):
    from agents.availability import provider_health
    return await provider_health()


@router.get("/healthz/service")
async def service_ready(db: DbSession):
    """Render readiness: this container's worker, database and persistent files."""
    import os
    import tempfile
    from sqlalchemy import select
    from db.models import WorkerState
    from orchestrator.runtime import utcnow, aware

    prefix = os.getenv("TRACEFORM_REQUIRED_WORKER_PREFIX")
    if not prefix:
        raise HTTPException(status_code=503, detail="Worker supervision is not configured.")

    async def check():
        last_seen = (await db.execute(select(WorkerState.last_seen_at).where(
            WorkerState.worker_id.startswith(prefix)
        ).order_by(WorkerState.last_seen_at.desc()).limit(1))).scalar_one_or_none()
        if last_seen is None or not 0 <= (utcnow() - aware(last_seen)).total_seconds() < 30:
            raise RuntimeError("worker unavailable")
        with tempfile.TemporaryFile(dir=os.environ["OBJECT_STORAGE_PATH"]) as probe:
            probe.write(b"storage probe")
            probe.flush()

    try:
        await asyncio.wait_for(check(), timeout=2)
    except Exception:
        raise HTTPException(status_code=503, detail="Service dependencies are unavailable.") from None
    return {"status": "ready", "database": "ok", "worker": "ok", "storage": "ok"}
