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
