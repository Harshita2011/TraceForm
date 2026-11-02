"""Database queue with compare-and-swap leases; the API never owns execution tasks."""
import asyncio
import os
import socket
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, update
from db.models import DurableJob, Generation, LLMCall, ProviderConfiguration, WorkerState
from db.session import AsyncSessionLocal
from schemas.enums import GenerationStatus
from orchestrator.runtime import (RunContext, current_run, utcnow, aware, plan_fingerprint,
                                  JobCancelled, LeaseLost)


async def worker_seen(worker_id, factory):
    async with factory() as db:
        row = await db.get(WorkerState, worker_id)
        if row:
            row.last_seen_at = utcnow()
        else:
            db.add(WorkerState(worker_id=worker_id, last_seen_at=utcnow()))
        await db.commit()


async def recover_expired(factory=AsyncSessionLocal):
    async with factory() as db:
        expired = (await db.execute(select(DurableJob).where(
            DurableJob.status == "running", DurableJob.lease_until <= utcnow()))).scalars().all()
        for job in expired:
            won = await db.execute(update(DurableJob).where(DurableJob.generation_id == job.generation_id,
                DurableJob.status == "running", DurableJob.lease_token == job.lease_token,
                DurableJob.lease_until <= utcnow()).values(lease_token=None, worker_id=None)
                .execution_options(synchronize_session=False))
            if not won.rowcount:
                continue
            job.lease_token, job.worker_id = None, None
            calls = (await db.execute(select(LLMCall).where(LLMCall.generation_id == job.generation_id,
                                                          LLMCall.status.in_(["started", "uncertain", "failed"])))).scalars().all()
            generation = await db.get(Generation, job.generation_id)
            if job.cancel_requested:
                job.status, generation.status = "cancelled", GenerationStatus.CANCELLED
                job.message = "Cancelled. Provider requests already submitted may still be billed."
            elif calls or job.attempts >= 3:
                job.status, generation.status = "failed", GenerationStatus.FAILED
                job.message = ("The worker stopped during a provider request. Its outcome and charge are unknown. "
                               "Existing outputs are kept. Retry may incur a new charge." if calls else
                               "Recovery attempt limit reached. Existing outputs are kept; retry to continue.")
            else:
                job.status, generation.status = "queued", GenerationStatus.QUEUED
                job.message = "Worker interrupted. Resuming from saved provider responses and completed outputs."
            for call in calls:
                if call.status == "started":
                    call.status, call.finished_at = "uncertain", utcnow()
                    call.error = "Worker interrupted before the provider result could be saved."
        await db.commit()


async def claim_job(worker_id, factory=AsyncSessionLocal, lease_seconds=60):
    await recover_expired(factory)
    async with factory() as db:
        candidate = (await db.execute(select(DurableJob.generation_id).where(
            DurableJob.status == "queued", DurableJob.cancel_requested.is_(False)
        ).order_by(DurableJob.created_at).limit(1))).scalar_one_or_none()
        if not candidate:
            return None
        token = uuid4().hex
        won = await db.execute(update(DurableJob).where(DurableJob.generation_id == candidate,
            DurableJob.status == "queued", DurableJob.cancel_requested.is_(False)).values(
                status="running", worker_id=worker_id, lease_token=token,
                heartbeat_at=utcnow(), lease_until=utcnow() + timedelta(seconds=lease_seconds),
                attempts=DurableJob.attempts + 1))
        if not won.rowcount:
            await db.rollback()
            return None
        await db.commit()
        return candidate, token


async def _heartbeat(generation_id, token, worker_id, task, factory, lease_seconds):
    try:
        await _heartbeat_loop(generation_id, token, worker_id, task, factory, lease_seconds)
    except asyncio.CancelledError:
        raise
    except Exception:
        # A failed monitor must not leave execution running without lease renewal or cancellation checks.
        import logging
        logging.getLogger(__name__).exception('Worker heartbeat failed; stopping execution for durable recovery')
        task.cancel()
        raise


async def _heartbeat_loop(generation_id, token, worker_id, task, factory, lease_seconds):
    while not task.done():
        await asyncio.sleep(min(5, max(0.1, lease_seconds / 4)))
        await worker_seen(worker_id, factory)
        async with factory() as db:
            job = await db.get(DurableJob, generation_id)
            if not job or job.lease_token != token or job.cancel_requested:
                task.cancel()
                return
            changed = await db.execute(update(DurableJob).where(DurableJob.generation_id == generation_id,
                DurableJob.lease_token == token, DurableJob.status == "running",
                DurableJob.lease_until > utcnow()).values(heartbeat_at=utcnow(),
                    lease_until=utcnow() + timedelta(seconds=lease_seconds)).execution_options(synchronize_session=False))
            await db.commit()
            if not changed.rowcount:
                task.cancel()
                return


async def run_once(worker_id=None, factory=AsyncSessionLocal, pipeline=None, lease_seconds=60):
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    await worker_seen(worker_id, factory)
    claimed = await claim_job(worker_id, factory, lease_seconds)
    if not claimed:
        return False
    generation_id, token = claimed
    async with factory() as db:
        job = await db.get(DurableJob, generation_id)
        config = await db.get(ProviderConfiguration, job.configuration_id)
        plan_matches = job.plan_fingerprint == plan_fingerprint()
    context_token = current_run.set(RunContext(generation_id, token, config, factory))
    from teams.scope import workspace
    workspace_token = workspace.set(job.workspace_id)
    execution = None
    heartbeat = None
    try:
        if not plan_matches:
            raise RuntimeError("The pipeline version changed. Create a new run to use the updated version safely.")
        if pipeline is None:
            if job.task_kind == 'evaluation':
                from eval.measured import execute
                pipeline = execute
            elif job.task_kind == 'source_analysis':
                from synthesis.worker import execute
                pipeline = execute
            elif job.task_kind == 'version':
                from revisions.worker import execute
                pipeline = execute
            else:
                from orchestrator.jobs import _async_run_generation_pipeline
                pipeline = _async_run_generation_pipeline
        execution = asyncio.create_task(pipeline(None, str(generation_id)))
        heartbeat = asyncio.create_task(_heartbeat(generation_id, token, worker_id, execution, factory, lease_seconds))
        await asyncio.wait_for(execution, timeout=float(os.getenv("TRACEFORM_JOB_TIMEOUT_SECONDS", "1800")))
        async with factory() as db:
            from orchestrator.runtime import fence
            await fence(db)
            generation = await db.get(Generation, generation_id)
            job = await db.get(DurableJob, generation_id)
            if job and job.lease_token == token and job.cancel_requested:
                generation.status = GenerationStatus.CANCELLED
            await db.execute(update(DurableJob).where(DurableJob.generation_id == generation_id,
                DurableJob.lease_token == token, DurableJob.status == "running").values(
                    status="cancelled" if generation.status == GenerationStatus.CANCELLED else
                    "completed" if generation.status in (GenerationStatus.COMPLETED, GenerationStatus.PARTIAL_FAILURE) else "failed",
                    finished_at=utcnow(), lease_token=None, lease_until=None))
            await db.commit()
    except asyncio.CancelledError:
        async with factory() as db:
            job = await db.get(DurableJob, generation_id)
            if job and job.lease_token == token:
                # Stop gracefully but leave recovery decisions to the same durable recovery path.
                job.lease_until = utcnow() - timedelta(seconds=1)
                await db.commit()
        await recover_expired(factory)
        if asyncio.current_task().cancelling():
            raise
    except Exception as exc:
        from orchestrator.progress import failure_guidance
        message = str(exc) if not plan_matches else failure_guidance(exc)
        async with factory() as db:
            won = await db.execute(update(DurableJob).where(DurableJob.generation_id == generation_id,
                DurableJob.lease_token == token).values(status="failed", message=message,
                finished_at=utcnow(), lease_token=None, lease_until=None))
            if won.rowcount:
                generation = await db.get(Generation, generation_id)
                generation.status = GenerationStatus.FAILED
            await db.commit()
    finally:
        if heartbeat:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        current_run.reset(context_token)
        workspace.reset(workspace_token)
    await sync_artifact_costs(generation_id, factory)
    return True


async def sync_artifact_costs(generation_id, factory):
    """Derive display totals from saved calls, including every review/repair attempt."""
    from db.models import Artifact
    async with factory() as db:
        generation = await db.get(Generation, generation_id)
        calls = (await db.execute(select(LLMCall).where(LLMCall.generation_id == generation_id))).scalars().all()
        artifacts = (await db.execute(select(Artifact).where(Artifact.generation_id == generation_id))).scalars().all()
        shared = [c for c in calls if not c.output_type]
        def cost(rows):
            return sum((c.usage or {}).get("estimated_cost_usd") or 0 for c in rows)
        for artifact in artifacts:
            owned = [c for c in calls if c.output_type == artifact.output_type]
            history = [{"call_id": str(c.id), "stage": c.stage, "model": c.model, "provider": c.provider,
                        "pricing_version": c.pricing.get("version"), "status": c.status,
                        "usage": c.usage, "error": c.error} for c in owned]
            data = {"analyst_share": cost(shared) / max(1, len(generation.output_types)),
                    "execution_history": history, "usage_incomplete": any(c.status != "succeeded" or
                    not (c.usage or {}).get("usage_recorded", True) for c in owned + shared)}
            for stage, label in [("generation", "generation"), ("style_review", "style_review"),
                                 ("fact_review", "fact_review"), ("compliance_review", "compliance_review")]:
                data[label] = cost([c for c in owned if c.stage == stage])
            for stage, label in [("generation", "generator_tokens"), ("style_review", "style_tokens"),
                                 ("fact_review", "fact_tokens"), ("compliance_review", "compliance_tokens")]:
                data[label] = sum((c.usage or {}).get("input_tokens", 0) + (c.usage or {}).get("output_tokens", 0)
                                  for c in owned if c.stage == stage)
            data["total"] = cost(owned) + data["analyst_share"]
            artifact.cost = data
        await db.commit()


async def job_summary(db, generation_id):
    from sqlalchemy import func
    job = await db.get(DurableJob, generation_id)
    if not job:
        return None
    config = await db.get(ProviderConfiguration, job.configuration_id)
    generation = await db.get(Generation, generation_id)
    last_seen = (await db.execute(select(WorkerState.last_seen_at).order_by(
        WorkerState.last_seen_at.desc()).limit(1))).scalar_one_or_none()
    uncertain = (await db.execute(select(func.count(LLMCall.id)).where(
        LLMCall.generation_id == generation_id, LLMCall.status == "uncertain"))).scalar() or 0
    calls = (await db.execute(select(LLMCall).where(LLMCall.generation_id == generation_id))).scalars().all()
    return {"status": job.status, "attempts": job.attempts, "message": job.message,
            "cancel_requested": job.cancel_requested, "can_cancel": job.status in ("queued", "running") and not job.cancel_requested,
            "worker_online": bool(last_seen and (utcnow() - aware(last_seen)).total_seconds() < 30),
            "heartbeat_at": aware(job.heartbeat_at).isoformat() if job.heartbeat_at else None,
            "configuration_id": str(config.id), "provider": config.provider, "model": config.model,
            "pricing": config.pricing, "reserved_budget": job.reserved_budget,
            "budget_used": generation.budget_used, "budget_ceiling": generation.budget_ceiling,
            "budget_type": generation.budget_type, "budget_overrun": bool(generation.budget_ceiling is not None and generation.budget_used > generation.budget_ceiling),
            "uncertain_calls": uncertain, "call_count": len(calls),
            "usage_incomplete": any(c.status != "succeeded" or not (c.usage or {}).get("usage_recorded", True) for c in calls),
            "extraction_reused": job.extraction_reused}


async def run_forever(factory=AsyncSessionLocal, poll_seconds=1, worker_id=None):
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    while True:
        try:
            worked = await run_once(worker_id, factory)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Queue poll failed; will retry")
            worked = False
        if not worked:
            await asyncio.sleep(poll_seconds)
