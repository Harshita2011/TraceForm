"""
# §4 Orchestrator — Celery task definitions for the async generation pipeline.

Pipeline flow:
  POST /api/v1/generations
    → run_generation_pipeline.delay(generation_id)
        → run_analyst_stage (single task)
            → chord([run_generator_task × N]) | _finalize_generation

Reliability (§4):
  - Each task gets bounded retries with exponential backoff.
  - On retry exhaustion, the artifact/stage is marked FAILED — the rest of the batch is
    not cancelled. Generation.status becomes PARTIAL_FAILURE if ≥1 generator failed.
  - task_acks_late=True + task_reject_on_worker_lost=True (set in celery_app.py) ensure
    no tasks are silently lost if a worker process dies.

NOTE — Eager mode (task_always_eager=True) is set in tests so tasks run synchronously
in the test process without a real broker. This validates application logic for
dead-letter handling. Real retry/backoff timing is deferred to Phase 5 load tests
against real infrastructure (see docs/archive/phases/06_evaluation_security.md note).
"""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import UUID

import anthropic  # top-level import required for patch('orchestrator.jobs.anthropic.AsyncAnthropic')
import anthropic
from celery import group, chord
from celery.exceptions import Retry as CeleryRetry
from celery.utils.log import get_task_logger

from orchestrator.celery_app import celery_app

from db.session import AsyncSessionLocal
from agents.llm import create_llm_client, get_default_model
from orchestrator.runtime import current_run, current_stage, check_current, fence, BudgetLimitExceeded
from orchestrator.checkpoints import load_extraction, save_extraction
from orchestrator.progress import record_progress, failure_guidance, fail_active_stage
from agents.generators.base import GenericGeneratorAgent
from agents.analyst import AnalystAgent
from agents.reviewers import StyleReviewer, FactReviewer, ComplianceReviewer, StyleQualityReviewer
from synthesis.context import load_context, evidence_text
from cost.tracker import (
    tokens_to_cost,
    compute_analyst_cost_share,
    build_artifact_cost_breakdown,
)

logger = get_task_logger(__name__)

# --- Retry policy constants ---
_ANALYST_MAX_RETRIES = 3
_GENERATOR_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 5  # seconds; actual delay = _RETRY_BACKOFF_BASE * (2 ** retry_count)


def _sessions():
    context = current_run.get()
    return context.session_factory if context else AsyncSessionLocal


async def _progress(generation_id, stage, status, output_type=None, message=None):
    await check_current()
    current_stage.set((stage, output_type))
    await record_progress(generation_id, stage, status, output_type, message,
                          session_factory=_sessions())


def _run_async(coro):
    """
    Run an async coroutine from a sync Celery task context.

    In production: Celery workers have no running event loop, so a new loop is created.
    In tests (eager mode): pytest-asyncio runs a loop already, so we schedule the coro
    as a task on that loop using asyncio.ensure_future and drive it to completion.
    This is safe because Celery eager mode calls the task synchronously within the
    test's async context.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()


# ─────────────────────────────────────────────
# Entry point — enqueue the full pipeline
# ─────────────────────────────────────────────

def enqueue_generation(generation_id: str) -> str:
    """
    §4 — Enqueue the full generation pipeline.
    Called by POST /api/v1/generations after persisting the Generation row.
    Returns the task ID.
    """
    # The job row is committed atomically with the generation by the API.
    # Workers poll that row; this function is a compatibility notification boundary.
    return f"durable-{generation_id}"


async def _run_background_generation(generation_id: str) -> None:
    """Persist terminal failure even when extraction, reviews, or rendering crash."""
    try:
        await _async_run_generation_pipeline(None, generation_id)
    except Exception as exc:
        logger.exception("Background generation %s failed", generation_id)
        from db.models import Generation
        from schemas.enums import GenerationStatus
        async with _sessions()() as db:
            generation = await db.get(Generation, UUID(generation_id))
            if generation:
                generation.status = GenerationStatus.FAILED
                await fence(db)
                await db.commit()
        await fail_active_stage(generation_id, exc, session_factory=_sessions())


# ─────────────────────────────────────────────
# Task 1 — top-level pipeline orchestrator
# ─────────────────────────────────────────────

@celery_app.task(
    name="orchestrator.jobs.run_generation_pipeline",
    bind=True,
    max_retries=_ANALYST_MAX_RETRIES,
    default_retry_delay=_RETRY_BACKOFF_BASE,
)
def run_generation_pipeline(self, generation_id: str) -> None:
    """
    §4 — Orchestrate the full pipeline for one Generation.

    Steps:
      1. Load Generation + Source from DB.
      2. Run Analyst Agent → persist KnowledgeExtraction.
      3. Fan out Generator tasks in parallel via Celery group.
      4. Finalise Generation status.
    """
    _run_async(_async_run_generation_pipeline(self, generation_id))


async def _async_run_generation_pipeline(task, generation_id: str) -> None:
    from db.models import Generation, Source, KnowledgeExtractionModel
    from schemas.enums import GenerationStatus
    from agents.analyst.agent import AnalystAgent

    async with _sessions()() as db:
        generation = await db.get(Generation, UUID(generation_id))
        if generation is None:
            logger.error("Generation %s not found — aborting pipeline.", generation_id)
            return

        source = await load_context(db, generation)
        if source is None:
            logger.error("Source %s not found for generation %s.", generation.source_id, generation_id)
            generation.status = GenerationStatus.FAILED
            await fence(db)
            await db.commit()
            return

        # Mark running
        generation.status = GenerationStatus.RUNNING
        await fence(db)
        await db.commit()

    # --- Analyst Agent ---
    model = get_default_model()
    client = create_llm_client()
    analyst = AnalystAgent(client=client, model=model)

    await _progress(generation_id, "extract", "running")
    cached_extraction = await load_extraction(source, model, _sessions())
    try:
        if cached_extraction:
            extraction, ke_id = cached_extraction
            analyst_usage = {"input_tokens": 0, "output_tokens": 0}
        else:
            if len(getattr(source, 'documents', {})) > 1:
                from synthesis.extraction import analyzed_extraction
                async with _sessions()() as db:
                    extraction = await analyzed_extraction(db, generation, source)
                analyst_usage = {'input_tokens':0,'output_tokens':0}
            else:
                extraction, analyst_usage = await analyst.extract(source)
    except Exception as exc:
        await _progress(generation_id, "extract", "failed", message=failure_guidance(exc))
        logger.error("Analyst Agent failed for generation %s: %s", generation_id, exc, exc_info=True)
        if task is not None and hasattr(task, "retry"):
            try:
                retries = getattr(task.request, "retries", 0)
                raise task.retry(exc=exc, countdown=_RETRY_BACKOFF_BASE * (2 ** retries))
            except Exception:
                pass
        async with _sessions()() as db:
            gen = await db.get(Generation, UUID(generation_id))
            if gen:
                gen.status = GenerationStatus.FAILED
                await fence(db)
                await db.commit()
        return

    await _progress(generation_id, "extract", "done")
    # --- Record Analyst Usage on Generation ---
    analyst_tokens = (analyst_usage.get("input_tokens", 0) + analyst_usage.get("output_tokens", 0)) if analyst_usage else 0
    analyst_cost = tokens_to_cost(analyst_usage, model)
    await _atomic_record_usage(generation_id, analyst_tokens, analyst_cost)

    # The extraction checkpoint is fenced and committed before output fan-out.
    if len(getattr(source, 'documents', {})) > 1:
        from synthesis.extraction import resolved
        extraction = resolved(extraction, (generation.synthesis or {}).get('resolutions', {}))
        ke_id = await save_extraction(source, extraction, model, _sessions())
    elif not cached_extraction:
        ke_id = await save_extraction(source, extraction, model, _sessions())

    # --- Fan-out generator tasks in PARALLEL (§4 latency requirement) ---
    output_types: list[str] = generation.output_types
    analyst_cost_per_type = compute_analyst_cost_share(analyst_usage, len(output_types), model)

    is_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
    if task is None or is_eager:
        await asyncio.gather(*[
            _async_run_generator_task(
                None,
                generation_id=generation_id,
                ke_id=ke_id,
                output_type=ot,
                model=model,
                analyst_cost_share=analyst_cost_per_type,
            )
            for ot in output_types
        ])
    else:
        generator_tasks = group(
            run_generator_task.s(
                generation_id=generation_id,
                ke_id=ke_id,
                output_type=ot,
                model=model,
                analyst_cost_share=analyst_cost_per_type,
            )
            for ot in output_types
        )
        result = generator_tasks.apply_async()
        result.get(disable_sync_subtasks=False)

    # --- Finalise Generation status ---
    await _finalize_generation(generation_id)


async def _finalize_generation(generation_id: str) -> None:
    """
    Finalize generation status after all parallel artifact generators complete.
    """
    from db.models import Generation, Artifact
    from schemas.enums import GenerationStatus, ArtifactReviewStatus
    from sqlalchemy import select

    async with _sessions()() as db:
        gen = await db.get(Generation, UUID(generation_id))
        if gen is None:
            return

        art_res = await db.execute(
            select(Artifact).where(Artifact.generation_id == UUID(generation_id))
        )
        artifacts = list(art_res.scalars().all())

        if not artifacts:
            gen.status = GenerationStatus.FAILED
        elif any(a.review_status == ArtifactReviewStatus.FAILED for a in artifacts):
            if all(a.review_status == ArtifactReviewStatus.FAILED for a in artifacts):
                gen.status = GenerationStatus.FAILED
            else:
                gen.status = GenerationStatus.PARTIAL_FAILURE
        elif (
            {a.output_type for a in artifacts} != set(gen.output_types or [])
            or any(a.review_status != ArtifactReviewStatus.PASSED for a in artifacts)
        ):
            gen.status = GenerationStatus.PARTIAL_FAILURE
        else:
            gen.status = GenerationStatus.COMPLETED

        # Cross-Artifact Differentiation Validation
        from agents.generators.differentiation import validate_artifact_batch_differentiation
        art_map = {a.output_type: (a.content or "") for a in artifacts if a.content}
        if len(art_map) > 1:
            diff_report = validate_artifact_batch_differentiation(art_map)
            logger.info(
                "Generation %s differentiation report: is_differentiated=%s max_similarity=%.3f min_diff=%.1f flagged=%d",
                generation_id, diff_report.is_differentiated, diff_report.max_similarity, diff_report.min_differentiation_score, len(diff_report.flagged_pairs)
            )
            for a in artifacts:
                u_score = diff_report.uniqueness_scores.get(a.output_type)
                if u_score:
                    results = list(a.review_results or [])
                    meta_idx = next((i for i, r in enumerate(results) if isinstance(r, dict) and "_traceform_meta" in r), None)
                    if meta_idx is not None:
                        meta_copy = dict(results[meta_idx]["_traceform_meta"])
                        meta_copy["differentiation_measured"] = True
                        meta_copy["uniqueness_score"] = u_score.uniqueness_score
                        meta_copy["differentiation_score"] = u_score.uniqueness_score
                        meta_copy["is_generic"] = u_score.is_generic
                        meta_copy["role"] = u_score.role
                        meta_copy["audience"] = u_score.audience
                        meta_copy["purpose"] = u_score.purpose
                        meta_copy["writing_style"] = u_score.writing_style
                        meta_copy["flagged_reasons"] = u_score.flagged_reasons
                        results[meta_idx] = {"_traceform_meta": meta_copy}
                    else:
                        results.append({
                            "_traceform_meta": {
                                "differentiation_measured": True,
                                "uniqueness_score": u_score.uniqueness_score,
                                "differentiation_score": u_score.uniqueness_score,
                                "is_generic": u_score.is_generic,
                                "role": u_score.role,
                                "audience": u_score.audience,
                                "purpose": u_score.purpose,
                                "writing_style": u_score.writing_style,
                                "flagged_reasons": u_score.flagged_reasons,
                            }
                        })
                    a.review_results = results

        await fence(db)
        await db.commit()
        logger.info("Generation %s finalized with status=%s (%d artifacts)", generation_id, gen.status.value, len(artifacts))


# ─────────────────────────────────────────────
# Task 2 — single generator task
# ─────────────────────────────────────────────

@celery_app.task(
    name="orchestrator.jobs.run_generator_task",
    bind=True,
    max_retries=_GENERATOR_MAX_RETRIES,
    default_retry_delay=_RETRY_BACKOFF_BASE,
)
def run_generator_task(
    self,
    *,
    generation_id: str,
    ke_id: str,
    output_type: str,
    model: str,
    analyst_cost_share: float,
) -> None:
    _run_async(_async_run_generator_task(
        self, generation_id, ke_id, output_type, model, analyst_cost_share
    ))


async def _async_run_generator_task(task, generation_id, ke_id, output_type, model, analyst_cost_share):
    """Keep one output's review or delivery failure from cancelling sibling outputs."""
    try:
        await _async_generate_output(task, generation_id, ke_id, output_type, model, analyst_cost_share)
    except CeleryRetry:
        raise
    except Exception as exc:
        logger.exception("Output %s failed in generation %s", output_type, generation_id)
        await fail_active_stage(generation_id, exc, session_factory=_sessions(), output_type=output_type)
        from db.models import Artifact
        from schemas.enums import ArtifactReviewStatus
        from sqlalchemy import select
        async with _sessions()() as db:
            existing = (await db.execute(select(Artifact).where(
                Artifact.generation_id == UUID(generation_id), Artifact.output_type == output_type
            ))).scalar_one_or_none()
            if existing is None:
                db.add(Artifact(generation_id=UUID(generation_id), output_type=output_type,
                                review_status=ArtifactReviewStatus.FAILED,
                                review_results=[{"error": failure_guidance(exc)}]))
            else:
                existing.review_status = ArtifactReviewStatus.FAILED
            await fence(db)
            await db.commit()


async def _persist_artifact(db, artifact):
    """A resumed job replaces its unfinished checkpoint; passed outputs retain their ID."""
    if current_run.get():
        from db.models import Artifact
        from sqlalchemy import select
        await fence(db)
        existing = (await db.execute(select(Artifact).where(
            Artifact.generation_id == artifact.generation_id,
            Artifact.output_type == artifact.output_type))).scalars().first()
        if existing:
            for column in Artifact.__table__.columns:
                if column.name not in {"id", "generation_id", "output_type", "created_at", "workspace_id"}:
                    setattr(existing, column.name, getattr(artifact, column.name))
            return existing
    db.add(artifact)
    return artifact


async def _async_generate_output(
    task,
    generation_id: str,
    ke_id: str,
    output_type: str,
    model: str,
    analyst_cost_share: float,
) -> None:
    from datetime import datetime, timezone
    from db.models import Artifact, Generation, KnowledgeExtractionModel, Source
    from schemas.enums import ArtifactReviewStatus
    from schemas.knowledge import KnowledgeExtraction
    from schemas.generation import GenerationParams

    await check_current()
    if current_run.get():
        from sqlalchemy import select
        async with _sessions()() as db:
            existing = (await db.execute(select(Artifact).where(Artifact.generation_id == UUID(generation_id),
                Artifact.output_type == output_type))).scalars().first()
            if existing and existing.review_status == ArtifactReviewStatus.PASSED:
                return

    # 1. Stage-Boundary Check: Check budget BEFORE launching generator (§4)
    if await _is_budget_exceeded(generation_id):
        await _progress(generation_id, "generate", "failed", output_type,
                        "The budget was reached before this output started. Raise the budget in a new generation to continue.")
        logger.warning("Generation %s budget exceeded before generator '%s' — marking BUDGET_EXCEEDED.", generation_id, output_type)
        async with _sessions()() as db:
            artifact = Artifact(
                generation_id=UUID(generation_id),
                output_type=output_type,
                content=None,
                review_status=ArtifactReviewStatus.BUDGET_EXCEEDED,
                review_results=[{"reason": "Budget cap reached before generation started.", "skipped": True}],
                cost=build_artifact_cost_breakdown(analyst_cost_share, None, None, None, None, None, model),
                retry_count=0,
                counted_as_eval_failure=False,
            )
            artifact = await _persist_artifact(db, artifact)
            await fence(db)
            await db.commit()
        return

    async with _sessions()() as db:
        ke_row = await db.get(KnowledgeExtractionModel, UUID(ke_id))
        generation = await db.get(Generation, UUID(generation_id))
        if ke_row is None or generation is None:
            logger.error(
                "Missing KE or Generation for generator task: ke_id=%s generation_id=%s",
                ke_id, generation_id,
            )
            return

        source = await load_context(db, generation)

        sens_val = source.sensitivity.value if source and hasattr(source.sensitivity, "value") else (source.sensitivity if source else "public")
        sens_src = source.sensitivity_source.value if source and hasattr(source.sensitivity_source, "value") else (source.sensitivity_source if source else "classifier")
        sens_conf = source.sensitivity_confidence if source else 0.5

        extraction = KnowledgeExtraction(
            conflicts=ke_row.conflicts or [], source_documents=ke_row.source_documents or [],
            summary=ke_row.summary,
            entities=ke_row.entities,
            facts=ke_row.facts,
            relationships=ke_row.relationships,
            domain=ke_row.domain,
            source_tone=ke_row.source_tone,
            sensitivity=sens_val,
            sensitivity_source=sens_src,
            sensitivity_confidence=sens_conf,
        )
        params = GenerationParams(**generation.params)

    client = create_llm_client()
    generator = GenericGeneratorAgent(output_type_key=output_type, client=client, model=model)

    execution_history: list[dict] = []
    regeneration_usage: dict | None = None

    await _progress(generation_id, "generate", "running", output_type)
    try:
        result = await generator.generate(context=extraction, params=params)
        gen_tokens = result.token_usage.get("input_tokens", 0) + result.token_usage.get("output_tokens", 0)
        gen_cost = tokens_to_cost(result.token_usage, model)
        await _atomic_record_usage(generation_id, gen_tokens, gen_cost)
        execution_history.append({
            "attempt_number": 1,
            "stage": "generation",
            "token_usage": result.token_usage,
            "cost": gen_cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outcome": "completed",
        })
    except Exception as exc:
        await _progress(generation_id, "generate", "failed", output_type, failure_guidance(exc))
        retries = getattr(task.request, "retries", 0) if (task is not None and hasattr(task, "request")) else 0
        logger.warning(
            "Generator '%s' failed (attempt %d/%d): %s",
            output_type, retries + 1, _GENERATOR_MAX_RETRIES + 1, exc,
        )
        if task is not None and hasattr(task, "retry"):
            try:
                raise task.retry(exc=exc, countdown=_RETRY_BACKOFF_BASE * (2 ** retries))
            except task.MaxRetriesExceededError:
                pass

        logger.error(
            "Generator '%s' failed for generation %s — marking artifact FAILED.",
            output_type, generation_id,
        )
        async with _sessions()() as db:
            artifact = Artifact(
                generation_id=UUID(generation_id),
                output_type=output_type,
                content=None,
                review_status=ArtifactReviewStatus.BUDGET_EXCEEDED if isinstance(exc, BudgetLimitExceeded) else ArtifactReviewStatus.FAILED,
                review_results=[{"error": failure_guidance(exc), "dead_lettered": True}],
                cost=build_artifact_cost_breakdown(analyst_cost_share, None, None, None, None, None, model),
                retry_count=retries,
                counted_as_eval_failure=False,
            )
            artifact = await _persist_artifact(db, artifact)
            await fence(db)
            await db.commit()
        return

    await _progress(generation_id, "generate", "done", output_type)
    await _progress(generation_id, "review", "running", output_type)
    # Enrich facts_used with stable fact_source_id (§3.7)
    facts_used = _enrich_facts_used(result.facts_used, extraction, ke_id)
    _stamp_citations(facts_used, source)
    await _save_review_draft(generation_id, output_type, result.content, facts_used)

    # --- Phase 3 Review Layer ---
    effective_params = params.for_output_type(output_type)

    style_rev = StyleReviewer(client=client, model=model)
    fact_rev = FactReviewer(client=client, model=model)
    compliance_rev = ComplianceReviewer(client=client, model=model)

    style_res, fact_res, comp_res = await asyncio.gather(
        style_rev.review(result.content, extraction, effective_params),
        fact_rev.review(result.content, extraction, effective_params),
        compliance_rev.review(result.content, extraction, effective_params),
    )

    style_usage = style_res.details.get("token_usage", {})
    fact_usage = fact_res.details.get("token_usage", {})
    comp_usage = comp_res.details.get("token_usage", {})

    rev_tokens = (
        style_usage.get("input_tokens", 0) + style_usage.get("output_tokens", 0) +
        fact_usage.get("input_tokens", 0) + fact_usage.get("output_tokens", 0) +
        comp_usage.get("input_tokens", 0) + comp_usage.get("output_tokens", 0)
    )
    rev_cost = (
        tokens_to_cost(style_usage, model) +
        tokens_to_cost(fact_usage, model) +
        tokens_to_cost(comp_usage, model)
    )
    await _atomic_record_usage(generation_id, rev_tokens, rev_cost)

    from agents.reviewers.specialist import run_specialist_review
    spec_res = run_specialist_review(output_type, result.content or "")

    review_results = [
        style_res.model_dump(),
        fact_res.model_dump(),
        comp_res.model_dump(),
        spec_res.model_dump(),
    ]
    review_results.extend(_evidence_checks(result.content, facts_used, source, output_type, effective_params.sections))
    review_attempts = [{'attempt': 1, 'content_version': _content_version(result.content),
                        'checks': list(review_results)}]
    retry_count = 0
    counted_as_eval_failure = False

    # Check outcomes
    if not comp_res.passed:
        review_status = ArtifactReviewStatus.FAILED
    elif _blocking_failed(review_results):
        # Check budget before starting regeneration (§4 stage-boundary policy)
        if await _is_budget_exceeded(generation_id):
            logger.warning("Generation %s budget exceeded before regeneration for '%s' — marking BUDGET_EXCEEDED.", generation_id, output_type)
            review_status = ArtifactReviewStatus.BUDGET_EXCEEDED
            execution_history.append({
                "attempt_number": 2,
                "stage": "regeneration",
                "token_usage": {"input_tokens": 0, "output_tokens": 0},
                "cost": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "outcome": "budget_exceeded_before_regeneration",
            })
        else:
            retry_count = 1
            failing_claims = _correction_feedback(review_results)
            try:
                regen_result = await generator.generate(
                    context=extraction,
                    params=params,
                    correction_notes=failing_claims,
                )
                regeneration_usage = regen_result.token_usage
                regen_tokens = regen_result.token_usage.get("input_tokens", 0) + regen_result.token_usage.get("output_tokens", 0)
                regen_cost = tokens_to_cost(regen_result.token_usage, model)
                await _atomic_record_usage(generation_id, regen_tokens, regen_cost)

                result = regen_result
                facts_used = _enrich_facts_used(result.facts_used, extraction, ke_id)
                _stamp_citations(facts_used, source)
                await _save_review_draft(generation_id, output_type, result.content, facts_used, review_attempts)

                execution_history.append({
                    "attempt_number": 2,
                    "stage": "regeneration",
                    "token_usage": regen_result.token_usage,
                    "cost": regen_cost,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "outcome": "completed",
                })

                # Re-run all reviewers concurrently on regenerated content
                s_res2, f_res2, c_res2 = await asyncio.gather(
                    style_rev.review(result.content, extraction, effective_params),
                    fact_rev.review(result.content, extraction, effective_params),
                    compliance_rev.review(result.content, extraction, effective_params),
                )
                s2_usage = s_res2.details.get("token_usage", {})
                f2_usage = f_res2.details.get("token_usage", {})
                c2_usage = c_res2.details.get("token_usage", {})
                r2_tokens = (
                    s2_usage.get("input_tokens", 0) + s2_usage.get("output_tokens", 0) +
                    f2_usage.get("input_tokens", 0) + f2_usage.get("output_tokens", 0) +
                    c2_usage.get("input_tokens", 0) + c2_usage.get("output_tokens", 0)
                )
                r2_cost = (
                    tokens_to_cost(s2_usage, model) +
                    tokens_to_cost(f2_usage, model) +
                    tokens_to_cost(c2_usage, model)
                )
                await _atomic_record_usage(generation_id, r2_tokens, r2_cost)

                review_results = [
                    s_res2.model_dump(),
                    f_res2.model_dump(),
                    c_res2.model_dump(),
                ]
                review_results.append(run_specialist_review(output_type, result.content or '').model_dump())
                review_results.extend(_evidence_checks(result.content, facts_used, source, output_type, effective_params.sections))
                review_attempts.append({'attempt': 2, 'content_version': _content_version(result.content),
                                        'checks': list(review_results)})

                if not c_res2.passed:
                    review_status = ArtifactReviewStatus.FAILED
                elif _blocking_failed(review_results):
                    review_status = ArtifactReviewStatus.FAILED
                    counted_as_eval_failure = True
                else:
                    review_status = ArtifactReviewStatus.PASSED
            except Exception as regen_exc:
                logger.warning("Regeneration failed for '%s': %s", output_type, regen_exc)
                review_status = ArtifactReviewStatus.FAILED
                counted_as_eval_failure = True
                review_results.append({'reviewer_name': 'correction_reviewer', 'passed': False,
                    'reviewer_version': '1.0', 'details': {'reasoning': 'The correction attempt failed. Review the saved output before use.'}})
                review_attempts.append({'attempt': 2, 'content_version': _content_version(result.content),
                                        'checks': list(review_results), 'outcome': 'correction_failed'})
    else:
        review_status = ArtifactReviewStatus.PASSED

    # --- Quality Scoring & Blueprint Metadata (Phase X) ---
    from agents.generators.blueprints import get_blueprint
    from agents.generators.section_validator import validate_artifact_sections
    from cost.quality_scoring import calculate_artifact_quality_score

    bp = get_blueprint(output_type)
    sec_res = validate_artifact_sections(result.content or "", bp)
    q_score_breakdown = calculate_artifact_quality_score(
        content=result.content,
        section_compliance_score=sec_res.compliance_score,
        citations_count=len(facts_used),
        reviewer_outcomes=review_results,
    )

    traceform_meta = {
        "_traceform_meta": {
            "key_insights": result.key_insights,
            "blueprint_version": result.blueprint_version,
            "purpose": result.purpose,
            "target_audience": result.target_audience,
            "decision_focus": result.decision_focus,
            "quality_score": q_score_breakdown.composite_score,
            "quality_breakdown": q_score_breakdown.model_dump(),
            "format_meta": result.format_meta,
            "section_compliance": sec_res.compliance_score,
            "sections_found": sec_res.found_sections,
            "missing_sections": sec_res.missing_sections,
            "role": bp.role,
            "audience": bp.audience,
            "writing_style": bp.writing_style,
            "differentiation_score": None,
            "uniqueness_score": None,
            "is_generic": None,
        }
    }
    review_results.append(traceform_meta)
    review_results.append({'_review_attempts': review_attempts})

    await _progress(generation_id, "review", "done" if review_status == ArtifactReviewStatus.PASSED else "failed",
                    output_type, None if review_status == ArtifactReviewStatus.PASSED else
                    "This output needs attention. Open the review results to see which checks failed.")
    await _progress(generation_id, "deliver", "running", output_type)
    # --- Persist artifact with full cost breakdown & history ---
    cost = build_artifact_cost_breakdown(
        analyst_share=analyst_cost_share,
        generation_usage=result.token_usage,
        regeneration_usage=regeneration_usage,
        style_usage=style_usage,
        fact_usage=fact_usage,
        compliance_usage=comp_usage,
        model=model,
        execution_history=execution_history,
    )

    async with _sessions()() as db:
        gen = await db.get(Generation, UUID(generation_id))
        artifact = Artifact(
            generation_id=UUID(generation_id),
            output_type=output_type,
            content=result.content,
            review_status=review_status,
            review_results=review_results,
            facts_used=facts_used,
            cost=cost,
            retry_count=retry_count,
            counted_as_eval_failure=counted_as_eval_failure,
        )
        artifact = await _persist_artifact(db, artifact)

        version_entry = f"{output_type}@{result.prompt_version}"
        if gen:
            existing = gen.prompt_version or ""
            entries = set(existing.split("; ")) if existing else set()
            entries.add(version_entry)
            gen.prompt_version = "; ".join(sorted(entries))

            rev_versions = f"style@{style_rev.version}; fact@{fact_rev.version}; compliance@{compliance_rev.version}"
            gen.reviewer_version = rev_versions

        await fence(db)
        await db.commit()
        logger.info(
            "Artifact successfully persisted to DB: id=%s generation_id=%s output_type=%s status=%s",
            artifact.id, generation_id, output_type, getattr(review_status, "value", review_status),
        )

    if output_type == "presentation":
        await _render_pptx_if_needed(generation_id, result.content)

    await _progress(generation_id, "deliver", "done", output_type)


# ─────────────────────────────────────────────
# Task 3 — Fresh-budget Rerun
# ─────────────────────────────────────────────

@celery_app.task(name="orchestrator.jobs.run_rerun_artifact_task", bind=True)
def run_rerun_artifact_task(
    self,
    *,
    generation_id: str,
    output_type: str,
    budget_type: str = "tokens",
    budget_ceiling: float | None = None,
) -> None:
    _run_async(_async_run_rerun_artifact_task(
        self, generation_id, output_type, budget_type, budget_ceiling
    ))


async def _async_run_rerun_artifact_task(
    task,
    generation_id: str,
    output_type: str,
    budget_type: str = "tokens",
    budget_ceiling: float | None = None,
) -> None:
    """
    §4 — Rerun a skipped/failed artifact under an INDEPENDENT fresh budget allocation.
    """
    from datetime import datetime, timezone
    from db.models import Artifact, Generation, KnowledgeExtractionModel, Source
    from schemas.enums import ArtifactReviewStatus
    from schemas.knowledge import KnowledgeExtraction
    from schemas.generation import GenerationParams
    from sqlalchemy import select

    model = get_default_model()

    async with _sessions()() as db:
        generation = await db.get(Generation, UUID(generation_id))
        if generation is None:
            logger.error("Generation %s not found for rerun.", generation_id)
            return

        source = await load_context(db, generation)
        ke_res = await db.execute(
            select(KnowledgeExtractionModel).where(KnowledgeExtractionModel.source_id == generation.source_id)
        )
        ke_row = ke_res.scalar_one_or_none()
        if ke_row is None or source is None:
            logger.error("Missing KE or Source for rerun %s", generation_id)
            return

        generation.rerun_count = (generation.rerun_count or 0) + 1
        await fence(db)
        await db.commit()

        sens_val = source.sensitivity.value if hasattr(source.sensitivity, "value") else source.sensitivity
        sens_src = source.sensitivity_source.value if hasattr(source.sensitivity_source, "value") else source.sensitivity_source
        extraction = KnowledgeExtraction(
            summary=ke_row.summary,
            entities=ke_row.entities,
            facts=ke_row.facts,
            relationships=ke_row.relationships,
            domain=ke_row.domain,
            source_tone=ke_row.source_tone,
            sensitivity=sens_val or "public",
            sensitivity_source=sens_src or "classifier",
            sensitivity_confidence=source.sensitivity_confidence or 0.5,
        )
        params = GenerationParams(**generation.params)

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    generator = GenericGeneratorAgent(output_type_key=output_type, client=client, model=model)

    result = await generator.generate(context=extraction, params=params)

    execution_history = [{
        "attempt_number": 1,
        "stage": "rerun_generation",
        "token_usage": result.token_usage,
        "cost": tokens_to_cost(result.token_usage, model),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": "completed",
    }]

    facts_used = _enrich_facts_used(result.facts_used, extraction, str(ke_row.id))

    effective_params = params.for_output_type(output_type)
    style_rev = StyleReviewer(client=client, model=model)
    fact_rev = FactReviewer(client=client, model=model)
    compliance_rev = ComplianceReviewer(client=client, model=model)

    style_res, fact_res, comp_res = await asyncio.gather(
        style_rev.review(result.content, extraction, effective_params),
        fact_rev.review(result.content, extraction, effective_params),
        compliance_rev.review(result.content, extraction, effective_params),
    )

    style_usage = style_res.details.get("token_usage", {})
    fact_usage = fact_res.details.get("token_usage", {})
    comp_usage = comp_res.details.get("token_usage", {})

    review_results = [style_res.model_dump(), fact_res.model_dump(), comp_res.model_dump()]
    review_results.extend(_evidence_checks(result.content, facts_used, source, output_type, effective_params.sections))
    review_status = ArtifactReviewStatus.PASSED if all(r.get('passed') is True for r in review_results) else ArtifactReviewStatus.FAILED

    cost = build_artifact_cost_breakdown(
        analyst_share=0.0,
        generation_usage=result.token_usage,
        regeneration_usage=None,
        style_usage=style_usage,
        fact_usage=fact_usage,
        compliance_usage=comp_usage,
        model=model,
        execution_history=execution_history,
    )

    async with _sessions()() as db:
        art_res = await db.execute(
            select(Artifact).where(
                Artifact.generation_id == UUID(generation_id),
                Artifact.output_type == output_type,
            )
        )
        artifact = art_res.scalar_one_or_none()
        if artifact:
            artifact.content = result.content
            artifact.review_status = review_status
            artifact.review_results = review_results
            artifact.facts_used = facts_used
            artifact.cost = cost
        else:
            artifact = Artifact(
                generation_id=UUID(generation_id),
                output_type=output_type,
                content=result.content,
                review_status=review_status,
                review_results=review_results,
                facts_used=facts_used,
                cost=cost,
            )
            artifact = await _persist_artifact(db, artifact)
        await fence(db)
        await db.commit()

    await _finalize_generation(generation_id)


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────

def _enrich_facts_used(
    facts_used: list[dict] | None,
    extraction: Any,
    ke_id: str,
) -> list[dict]:
    """Enrich generator-cited facts with stable fact_source_id alongside citation spans."""
    enriched = []
    ext_facts = getattr(extraction, "facts", []) or []
    for idx, f in enumerate(facts_used or []):
        claim = f.get("claim", "")
        candidates = [ef for ef in ext_facts if
            (f.get('source_span') == ef.source_span or ef.claim == claim) and
            (not f.get('source_span') or f.get('source_span') == ef.source_span) and
            (not f.get('source_id') or not ef.source_id or f['source_id'] == ef.source_id)]
        keyed = next((ef for ef in ext_facts if ef.fact_key and ef.fact_key == f.get('fact_key')), None)
        matched = keyed or (candidates[0] if candidates and (len(candidates) == 1 or not any(ef.source_id for ef in candidates)) else None)
        if matched:
            fact_idx = ext_facts.index(matched)
            fact_source_id = f"fact_{ke_id}_{fact_idx}"
            source_span = matched.source_span
            start_char = f.get('start_char', matched.start_char)
            end_char = f.get('end_char', matched.end_char)
            confidence = matched.confidence
        else:
            fact_source_id = None
            source_span = f.get("source_span", claim)
            start_char = f.get("start_char")
            end_char = f.get("end_char")
            confidence = None

        enriched.append({
            **f,
            'anchor_resolution': matched.anchor_resolution if matched else 'unresolved',
            'model_start_char': matched.model_start_char if matched else None,
            'model_end_char': matched.model_end_char if matched else None,
            "fact_source_id": fact_source_id,
            "claim": claim,
            "source_span": source_span,
            "start_char": start_char,
            "end_char": end_char,
            "confidence": confidence,
            **({'fact_key':matched.fact_key, 'source_id':matched.source_id,
                'source_version':matched.source_version, 'anchors':matched.anchors,
                'start_char':matched.start_char, 'end_char':matched.end_char} if matched and matched.source_id else {}),
        })
    return enriched


def _content_version(content):
    from evidence.validation import version
    return version(content)


async def _save_review_draft(generation_id, output_type, content, facts, attempts=None):
    """Fence a visible, unreviewed checkpoint before any provider review can fail."""
    if not current_run.get():
        return
    from db.models import Artifact
    from schemas.enums import ArtifactReviewStatus
    async with _sessions()() as db:
        pending = [{'reviewer_name': 'pending_reviewer', 'passed': False, 'reviewer_version': '1.0',
                    'details': {'reasoning': 'Generated text is saved. Required reviews have not completed; do not treat this draft as verified.'}}]
        if attempts:
            pending.append({'_review_attempts': attempts})
        draft = Artifact(generation_id=UUID(generation_id), output_type=output_type, content=content,
                         facts_used=facts, review_status=ArtifactReviewStatus.PENDING, review_results=pending,
                         retry_count=len(attempts or []), counted_as_eval_failure=False)
        await _persist_artifact(db, draft)
        await fence(db)
        await db.commit()


def _evidence_checks(content, facts, source, output_type, sections):
    from evidence.validation import validate_evidence, VERSION
    from schemas.formats import validate_format
    _stamp_citations(facts, source)
    evidence = validate_evidence(content, facts, evidence_text(source),
                                 source.id if source else None)
    structural = validate_format(output_type, content or '', sections)
    results = [
        {'reviewer_name': 'evidence_reviewer', 'passed': evidence['passed'], 'reviewer_version': VERSION,
         'details': {'issues': [(f["message"] + (" Claim: " + f["claim"] if f.get("claim") else "")) for f in evidence['findings']],
                     'anchors_matched': evidence['anchors_matched'], 'anchors_total': evidence['anchors_total'],
                     'source_version': evidence['source_version'], 'content_version': evidence['content_version'],
                     'reasoning': evidence['limitation']}},
        {'reviewer_name': 'format_reviewer', 'passed': structural['passed'],
         'reviewer_version': structural['version'], 'details': structural}]
    if len(getattr(source, 'documents', {})) > 1:
        from synthesis.extraction import conflicts_check
        results.append(conflicts_check(content or '', facts, source.conflicts))
    return results


def _stamp_citations(facts, source):
    from evidence.validation import version
    for fact in facts:
        multiple = len(getattr(source, 'documents', {})) > 1
        if not multiple:
            fact.setdefault('source_id', str(source.id) if source else None)
            fact.setdefault('source_version', version(source.extracted_text if source else None))
        calculation = fact.get('calculation')
        operands = calculation.get('inputs', []) if isinstance(calculation, dict) else []
        for operand in operands if isinstance(operands, list) else []:
            if isinstance(operand, dict):
                if not multiple:
                    operand.setdefault('source_id', fact.get('source_id'))
                    operand.setdefault('source_version', fact.get('source_version'))


def _correction_feedback(reviews):
    notes = []
    for review in reviews:
        if review.get('passed') is True:
            continue
        details = review.get('details') or {}
        messages = details.get('failing_claims') or details.get('issues') or details.get('missing_sections') or [details.get('reasoning', 'Check failed')]
        notes.extend(f"{review['reviewer_name']}: {message}" for message in messages)
    return notes


def _blocking_failed(reviews):
    from evidence.validation import BLOCKING_REVIEWERS
    return any(r.get('reviewer_name') in BLOCKING_REVIEWERS and r.get('passed') is not True for r in reviews)


async def _atomic_record_usage(generation_id: str, tokens: int, cost: float) -> tuple[float, bool]:
    """Atomically record token usage and cost on Generation row."""
    from db.models import Generation
    from sqlalchemy import func, update, cast, Numeric, Float
    if current_run.get():
        # Durable execution records every actual call atomically, including retries/reviews.
        return 0.0, False
    async with _sessions()() as db:
        gen = await db.get(Generation, UUID(generation_id))
        if not gen:
            return 0.0, False
        inc = cost if gen.budget_type == "cost_usd" else tokens
        await db.execute(
            update(Generation)
            .where(Generation.id == UUID(generation_id))
            .values(
                total_tokens=Generation.total_tokens + tokens,
                total_cost_usd=cast(func.round(cast(Generation.total_cost_usd + cost, Numeric), 6), Float),
                budget_used=cast(func.round(cast(Generation.budget_used + inc, Numeric), 6), Float),
            )
        )
        await fence(db)
        await db.commit()
        await db.refresh(gen)
        is_exceeded = gen.budget_ceiling is not None and gen.budget_used > gen.budget_ceiling
        return gen.budget_used, is_exceeded



async def _is_budget_exceeded(generation_id: str) -> bool:
    """Check if Generation budget ceiling is currently exceeded."""
    from db.models import Generation
    async with _sessions()() as db:
        gen = await db.get(Generation, UUID(generation_id))
        if not gen or gen.budget_ceiling is None:
            return False
        return (gen.budget_used or 0.0) >= gen.budget_ceiling


async def _render_pptx_if_needed(generation_id: str, content_json_str: str) -> None:
    """Render PPTX from presentation content and update artifact.rendered_file_ref."""
    import json
    from db.models import Artifact
    from sqlalchemy import select

    try:
        content_data = json.loads(content_json_str) if isinstance(content_json_str, str) else content_json_str
    except Exception:
        logger.warning("Could not parse presentation content as JSON for PPTX rendering.")
        return

    try:
        from rendering.pptx import render_presentation
        from storage.local import save_rendered_file
        pptx_bytes = render_presentation(content_data)
        file_ref = save_rendered_file(pptx_bytes, f"presentation_{generation_id}.pptx")

        async with _sessions()() as db:
            result = await db.execute(
                select(Artifact).where(
                    Artifact.generation_id == UUID(generation_id),
                    Artifact.output_type == "presentation",
                )
            )
            artifact = result.scalar_one_or_none()
            if artifact:
                artifact.rendered_file_ref = file_ref
                await fence(db)
                await db.commit()
    except Exception as exc:
        logger.warning("PPTX rendering failed for generation %s: %s", generation_id, exc)


# Backward-compatible cost helpers for tests
def _tokens_to_cost(usage: dict, model: str) -> float:
    return tokens_to_cost(usage, model)


def _compute_analyst_cost_share(usage: dict, num_output_types: int, model: str) -> float:
    """§3.7 — Analyst cost divided equally across all output types in the Generation."""
    return _tokens_to_cost(usage, model) / max(num_output_types, 1)


def _build_artifact_cost(token_usage: dict, model: str, analyst_share: float) -> dict:
    gen_cost = _tokens_to_cost(token_usage, model)
    return {
        "analyst_share": analyst_share,
        "generation": gen_cost,
        "regeneration": 0.0,
        "style_review": 0.0,    # Phase 3
        "fact_review": 0.0,     # Phase 3
        "compliance_review": 0.0,  # Phase 3
        "total": round(analyst_share + gen_cost, 6),
    }
