"""Persistent progress; readers never infer concurrent stages from a job's overall status."""
from uuid import UUID

from sqlalchemy import select

from db.models import PipelineEvent
from db.session import AsyncSessionLocal

STAGES = ("ingest", "extract", "generate", "review", "deliver")


def failure_guidance(exc: Exception) -> str:
    from synthesis.context import SourceUnavailable
    if isinstance(exc, SourceUnavailable):
        return str(exc)
    while exc.__cause__ is not None:
        exc = exc.__cause__
    text = str(exc).lower()
    if "remaining budget" in text or "budget" in text and "reservation" in text:
        return "The remaining budget cannot cover the next step. Create a run with a larger budget to continue."
    if isinstance(exc, TimeoutError):
        return "The AI provider took too long to respond. Wait a moment, then retry."
    if any(code in text for code in ("429", "quota", "rate limit")):
        return "The AI provider's usage limit was reached. Check your quota, then retry."
    if any(code in text for code in ("503", "504", "timeout", "deadline", "high demand")):
        return "The AI provider is temporarily busy. Wait a moment, then retry."
    if any(code in text for code in ("404", "model no longer", "not_found")):
        return "The selected AI model is unavailable. Choose an available model in the server configuration, then retry."
    if any(code in text for code in ("401", "403", "api key", "permission_denied")):
        return "The AI provider rejected the credentials. Check the server API key and permissions, then retry."
    return "This step could not finish. Retry the generation; if it fails again, check the server logs."


async def record_progress(generation_id: str, stage: str, status: str,
                          output_type: str | None = None, message: str | None = None,
                          session_factory=None):
    async with (session_factory or AsyncSessionLocal)() as db:
        from orchestrator.runtime import fence
        await fence(db)
        db.add(PipelineEvent(generation_id=UUID(generation_id), stage=stage, status=status,
                             output_type=output_type, message=message))
        await db.commit()


async def fail_active_stage(generation_id: str, exc: Exception, session_factory=None, output_type=None):
    factory = session_factory or AsyncSessionLocal
    async with factory() as db:
        events = (await db.execute(select(PipelineEvent).where(
            PipelineEvent.generation_id == UUID(generation_id)
        ).order_by(PipelineEvent.created_at, PipelineEvent.id))).scalars().all()
    latest = {}
    for event in events:
        if output_type is None or event.output_type == output_type:
            latest[(event.stage, event.output_type)] = event
    active = [event for event in latest.values() if event.status == "running"]
    for event in active:
        await record_progress(generation_id, event.stage, "failed", event.output_type,
                              failure_guidance(exc), session_factory=factory)
    if not active:
        await record_progress(generation_id, "generate" if output_type else "extract", "failed",
                              output_type, failure_guidance(exc), session_factory=factory)


async def read_progress(db, generation):
    rows = (await db.execute(select(PipelineEvent).where(
        PipelineEvent.generation_id == generation.id
    ).order_by(PipelineEvent.created_at, PipelineEvent.id))).scalars().all()
    overall = getattr(generation.status, "value", generation.status)
    stages = []
    for name in STAGES:
        events = [row for row in rows if row.stage == name]
        latest = {}
        for event in events:
            latest[event.output_type or "stage"] = event
        values = list(latest.values())
        state = "queued"
        if name == "ingest":
            state = "done"
        if values:
            if any(e.status == "failed" for e in values):
                state = "failed"
            elif any(e.status == "running" for e in values):
                state = "running"
            elif name in ("generate", "review", "deliver") and len(latest) < len(generation.output_types):
                state = "running" if overall in ("running", "queued") else "queued"
            else:
                state = "done"
        elif not rows and overall == "completed":
            state = "done"  # Historical runs did not record stage events.
        stages.append({"name": name, "status": state,
                       "started_at": events[0].created_at.isoformat() if events else None,
                       "ended_at": events[-1].created_at.isoformat() if events and state in ("done", "failed") else None,
                       "parallel_tasks": [{"label": key.replace('_', ' ').title(), "status": e.status}
                                          for key, e in latest.items() if key != "stage"]})
    final_events = {}
    for row in rows:
        final_events[(row.stage, row.output_type)] = row
    errors = [r for r in final_events.values() if r.status == "failed" and r.message]
    errors.sort(key=lambda r: r.created_at)
    return {"generation_id": str(generation.id), "stages": stages,
            "error": errors[-1].message if errors else (
                "This earlier run failed before progress tracking was available. Retry to run it again."
                if overall == "failed" else None)}
