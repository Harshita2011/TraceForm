"""Fenced job execution, durable provider-call checkpoints and atomic budget reservations."""
import asyncio
import hashlib
import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from db.models import DurableJob, Generation, LLMCall
from db.session import AsyncSessionLocal

current_run = ContextVar("traceform_run", default=None)
current_stage = ContextVar("traceform_stage", default=("extract", None))


class JobCancelled(asyncio.CancelledError):
    pass


class LeaseLost(asyncio.CancelledError):
    pass


class UncertainCall(RuntimeError):
    pass


class BudgetLimitExceeded(RuntimeError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


@lru_cache(maxsize=1)
def plan_fingerprint():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for directory in ("agents", "schemas", "config", "orchestrator", "evidence", "revisions", "synthesis", "teams", "security", "eval"):
        for path in sorted((root / directory).rglob("*")):
            if path.suffix in {".py", ".yaml"}:
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


@dataclass
class RunContext:
    generation_id: UUID
    lease_token: str
    configuration: object = field(repr=False)
    session_factory: object = field(default=AsyncSessionLocal, repr=False)


async def check_current():
    context = current_run.get()
    if not context:
        return
    async with context.session_factory() as db:
        from synthesis.context import assert_current
        await assert_current(db, context.generation_id)
        job = await db.get(DurableJob, context.generation_id)
        if job and job.cancel_requested:
            raise JobCancelled("Cancellation requested")
        if not job or job.status != "running" or job.lease_token != context.lease_token or aware(job.lease_until) <= utcnow():
            raise LeaseLost("Worker ownership expired")


async def fence(db):
    """Take the job-row write lock in the same transaction as a checkpoint/artifact write."""
    context = current_run.get()
    if context:
        from synthesis.context import assert_current
        await assert_current(db, context.generation_id)
        won = await db.execute(update(DurableJob).where(DurableJob.generation_id == context.generation_id,
            DurableJob.lease_token == context.lease_token, DurableJob.status == "running",
            DurableJob.cancel_requested.is_(False), DurableJob.lease_until > utcnow()).values(
                heartbeat_at=DurableJob.heartbeat_at).execution_options(synchronize_session=False))
        if not won.rowcount:
            await db.rollback()
            raise LeaseLost()


async def tracked_call(invoke, *, model, system_prompt, user_content, max_tokens, temperature, json_mode, purpose=None):
    context = current_run.get()
    await check_current()
    stage, output_type = current_stage.get()
    stage = purpose or stage
    configuration = context.configuration
    fingerprint = hashlib.sha256(json.dumps([stage, output_type, configuration.provider, model,
        system_prompt, user_content, max_tokens, temperature, json_mode], sort_keys=True).encode()).hexdigest()
    async with context.session_factory() as db:
        cached = (await db.execute(select(LLMCall).where(LLMCall.generation_id == context.generation_id,
                                                        LLMCall.fingerprint == fingerprint))).scalar_one_or_none()
        if cached:
            if cached.status == "succeeded":
                return cached.response_text, cached.usage
            raise UncertainCall("A prior provider call has no safely reusable result. Retry as a new run; the prior call may have been billed.")
        generation = await db.get(Generation, context.generation_id)
        # This is an admission estimate, not a claim to exact tokenizer equivalence.
        input_estimate = max(1, len((system_prompt + user_content).encode()) // 2)
        rates = configuration.pricing
        reservation = ((input_estimate * rates["input"] + max_tokens * rates["output"]) / 1_000_000
                       if generation.budget_type == "cost_usd" else input_estimate + max_tokens)
        predicate = [DurableJob.generation_id == context.generation_id,
                     DurableJob.lease_token == context.lease_token, DurableJob.status == "running",
                     DurableJob.cancel_requested.is_(False), DurableJob.lease_until > utcnow()]
        if generation.budget_ceiling is not None:
            used = select(Generation.budget_used).where(Generation.id == context.generation_id).scalar_subquery()
            predicate.append(DurableJob.reserved_budget + used + reservation <= generation.budget_ceiling)
        admitted = await db.execute(update(DurableJob).where(*predicate).values(
            reserved_budget=DurableJob.reserved_budget + reservation))
        if not admitted.rowcount:
            await db.rollback()
            await check_current()
            raise BudgetLimitExceeded("The remaining budget cannot cover this step's reservation. Create a run with a larger budget to continue.")
        call = LLMCall(generation_id=context.generation_id, fingerprint=fingerprint, stage=stage,
                       output_type=output_type, status="started", model=model, provider=configuration.provider,
                       pricing=dict(rates), reservation=reservation)
        db.add(call)
        await db.commit()
        call_id = call.id
    try:
        text, usage = await invoke()
        await check_current()
    except (asyncio.CancelledError, Exception) as exc:
        # Cancellation/transport errors do not prove the provider did not execute the call.
        async with context.session_factory() as db:
            call = await db.get(LLMCall, call_id)
            call.status = "uncertain" if isinstance(exc, asyncio.CancelledError) else "failed"
            from orchestrator.progress import failure_guidance
            call.error = ("The provider may still bill this interrupted request."
                          if isinstance(exc, asyncio.CancelledError) else failure_guidance(exc))
            call.finished_at = utcnow()
            await db.commit()
        raise
    known = usage.get("usage_recorded", True)
    input_tokens, output_tokens = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    cost = round((input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000, 8)
    usage = {**usage, "model": model, "provider": configuration.provider,
             "pricing": dict(rates), "estimated_cost_usd": cost if known else None}
    async with context.session_factory() as db:
        await fence(db)
        job = await db.get(DurableJob, context.generation_id)
        if job.lease_token != context.lease_token or job.cancel_requested:
            raise LeaseLost()
        call = await db.get(LLMCall, call_id)
        call.status, call.response_text, call.usage = "succeeded", text, usage
        call.finished_at = utcnow()
        if known:
            await db.execute(update(DurableJob).where(DurableJob.generation_id == context.generation_id,
                DurableJob.lease_token == context.lease_token).values(
                    reserved_budget=DurableJob.reserved_budget - reservation))
            generation = await db.get(Generation, context.generation_id)
            increment = cost if generation.budget_type == "cost_usd" else input_tokens + output_tokens
            await db.execute(update(Generation).where(Generation.id == context.generation_id).values(
                budget_used=Generation.budget_used + increment,
                total_tokens=Generation.total_tokens + input_tokens + output_tokens,
                total_cost_usd=Generation.total_cost_usd + cost))
        await db.commit()
    return text, usage
