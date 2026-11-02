"""
# §3.11 Generations API — Phase 2: async generation via Celery.

Changes from Phase 1:
  POST /api/v1/generations → 202 Accepted (creates Generation row + enqueues Celery task)
  GET  /api/v1/generations/{id} → reflects live async status (queued → running → completed/partial_failure)
  GET  /api/v1/generations/{id}/artifacts/{type} → unchanged
  GET  /api/v1/history → list generations with optional filters (status, output_type, date range)
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Header, status
from typing import Annotated
import hashlib
import json
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from agents.generators.base import load_output_type_config
from api.dependencies import CurrentOperator, DbSession, ReviewOperator
from db.models import Artifact, ComplianceOverride, Generation, Source, DurableJob, JobRequest
from synthesis.context import load_context, selected_sources, save_manifest, document_rows, SourceUnavailable
from orchestrator.jobs import enqueue_generation, run_rerun_artifact_task
from schemas.enums import ArtifactReviewStatus, GenerationStatus
from schemas.generation import (
    ArtifactResponse,
    ComplianceOverrideRequest,
    ComplianceOverrideResponse,
    FeedbackRequest,
    FeedbackResponse,
    GenerationAcceptedResponse,
    GenerationRequest,
    GenerationResponse,
    HistoryResponse,
    RerunRequest,
    RerunResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generations", tags=["generations"])


async def _check_version_owner(db, generation_id, operator):
    from teams.scope import team
    if team():
        if not await db.get(Generation,generation_id):raise HTTPException(404,'Generation not found.')
        return
    generation = await db.get(Generation, generation_id)
    if generation and generation.synthesis and generation.synthesis.get('owner') != operator:
        raise HTTPException(404, 'Generation not found.')
    from db.models import VersionOperation
    operation = await db.get(VersionOperation, generation_id)
    if operation and operation.owner != operator:
        raise HTTPException(404, 'Generation not found.')


@router.get("/formats")
async def output_formats(operator: CurrentOperator):
    from schemas.formats import format_catalog
    return format_catalog()


# ─────────────────────────────────────────────────────────────────
# POST /api/v1/generations  →  202 Accepted
# ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=GenerationAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    request: GenerationRequest,
    db: DbSession,
    operator: CurrentOperator,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> GenerationAcceptedResponse:
    """
    §3.11 / §4 — Enqueue an async generation pipeline with optional budget cap.
    """
    scope = db.info.get("submission_scope", "create")
    from teams.scope import workspace
    scope = f'{workspace.get() or "legacy"}:{scope}'
    payload_hash = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    key_hash = hashlib.sha256(f"{operator}:{scope}:{idempotency_key}".encode()).hexdigest() if idempotency_key else None
    if key_hash:
        previous = await db.get(JobRequest, key_hash)
        if previous:
            if previous.payload_hash != payload_hash:
                raise HTTPException(status_code=409, detail="This request key was already used with different settings.")
            original = await db.get(Generation, previous.generation_id)
            return _accepted(original, "Existing run returned; no duplicate work was queued.")

    source = await db.get(Source, request.source_ids[0] if request.source_ids else request.source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source {request.source_id} not found.",
        )

    from api.routes.sources import usable
    if not usable(source):
        raise HTTPException(422, "Choose a ready source containing extracted text. Restore removed sources in the library first.")

    for output_type in request.output_types:
        try:
            load_output_type_config(output_type)
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    from agents.llm import get_default_model
    from agents.availability import provider_health
    from config.provider import current_configuration
    configuration, _ = await current_configuration(db)
    combined_sources = None
    synthesis_settings = None
    if len(request.source_ids) > 1:
        from api.routes.synthesis import admitted_analysis
        combined_sources = await selected_sources(db, request.source_ids, True)
        synthesis_settings = await admitted_analysis(db, request, operator, configuration)
    health = await provider_health(configuration)
    if not health["available"]:
        raise HTTPException(status_code=503, detail=health["message"])
    model = configuration.model

    prompt_version_entries = []
    for ot in request.output_types:
        config = load_output_type_config(ot)
        version = config.get("prompt_template_version", "unknown")
        prompt_version_entries.append(f"{ot}@{version}")
    pinned_prompt_version = "; ".join(sorted(prompt_version_entries))

    from sqlalchemy import update
    locked = await db.execute(update(Source).where(Source.id == source.id, Source.deleted_at.is_(None)).values(filename=Source.filename))
    if not locked.rowcount:
        raise HTTPException(409, "This source was removed. Restore it before creating a run.")

    generation = Generation(
        synthesis=synthesis_settings,
        source_id=source.id,
        output_types=request.output_types,
        params=request.params.model_dump(),
        model_version=model,
        prompt_version=pinned_prompt_version,
        reviewer_version="unset",
        status=GenerationStatus.QUEUED,
        budget_type=request.budget_type,
        budget_ceiling=request.budget_ceiling,
        budget_used=0.0,
        total_tokens=0,
        total_cost_usd=0.0,
        rerun_count=0,
    )
    db.add(generation)
    await db.flush()
    await db.refresh(generation)
    if combined_sources:
        await save_manifest(db, generation.id, combined_sources)

    from orchestrator.runtime import plan_fingerprint
    db.add(DurableJob(generation_id=generation.id, configuration_id=configuration.id,
        plan_fingerprint=plan_fingerprint(), parent_generation_id=db.info.get("resume_parent") or request.analysis_id))
    if key_hash:
        db.add(JobRequest(key_hash=key_hash, payload_hash=payload_hash, generation_id=generation.id))
    try:
        # The generation, job and idempotency claim commit together.
        await db.commit()
    except IntegrityError:
        await db.rollback()
        previous = await db.get(JobRequest, key_hash) if key_hash else None
        if not previous or previous.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Request conflict; retry with the same request key.")
        original = await db.get(Generation, previous.generation_id)
        return _accepted(original, "Existing run returned; no duplicate work was queued.")
    task_id = enqueue_generation(str(generation.id))
    logger.info(
        "Generation %s queued: output_types=%s budget_type=%s budget_ceiling=%s task_id=%s",
        generation.id, request.output_types, request.budget_type, request.budget_ceiling, task_id,
    )

    return _accepted(generation, "Queued durably. The worker will process this run independently of the API.")


def _accepted(generation, message):
    return GenerationAcceptedResponse(id=generation.id, status=generation.status,
        prompt_version=generation.prompt_version, model_version=generation.model_version, message=message)


async def _selection_request(db, generation):
    if not generation.synthesis or not generation.synthesis.get('analysis_id'): return {}
    return {'source_ids':[row.source_id for row in await document_rows(db, generation.id)],
            'analysis_id':generation.synthesis['analysis_id'], 'conflict_resolutions':generation.synthesis['resolutions']}



@router.post("/{generation_id}/retry", response_model=GenerationAcceptedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def retry_generation(generation_id: UUID, db: DbSession, operator: CurrentOperator,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None):
    """Start a new run with the saved settings, requesting only outputs that did not pass."""
    await _check_version_owner(db, generation_id, operator)
    generation = await db.get(Generation, generation_id)
    if generation and generation.kind != 'generation':
        raise HTTPException(409, 'Start a new version task from the saved version.')
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found.")
    if generation.status in (GenerationStatus.QUEUED, GenerationStatus.RUNNING, GenerationStatus.PENDING):
        raise HTTPException(status_code=409, detail="This generation is still running.")
    artifacts = (await db.execute(select(Artifact).where(
        Artifact.generation_id == generation_id))).scalars().all()
    passed = {a.output_type for a in artifacts if a.review_status == ArtifactReviewStatus.PASSED}
    outputs = [t for t in generation.output_types if t not in passed]
    if not outputs:
        raise HTTPException(status_code=409, detail="All outputs passed. Create a new generation to make a different version.")
    db.info.update(submission_scope=f"retry:{generation_id}", resume_parent=generation_id)
    try:
        return await create_generation(GenerationRequest(
        **await _selection_request(db, generation),
        source_id=generation.source_id, output_types=outputs, params=generation.params or {},
        budget_type=generation.budget_type or "tokens", budget_ceiling=generation.budget_ceiling,
        ), db, operator, idempotency_key)
    finally:
        db.info.pop("submission_scope", None)
        db.info.pop("resume_parent", None)



@router.post("/{generation_id}/regenerate", response_model=GenerationAcceptedResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def regenerate_output(generation_id: UUID, output_type: str, db: DbSession, operator: CurrentOperator,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None):
    """Generate a new version without changing the original output or its review history."""
    await _check_version_owner(db, generation_id, operator)
    original = await db.get(Generation, generation_id)
    if original and original.kind != 'generation':
        raise HTTPException(409, 'Regenerate from the saved version workspace.')
    if original is None:
        raise HTTPException(status_code=404, detail="Generation not found.")
    if output_type not in original.output_types:
        raise HTTPException(status_code=422, detail="Choose an output format from the original run.")
    if original.status in (GenerationStatus.RUNNING, GenerationStatus.QUEUED, GenerationStatus.PENDING):
        raise HTTPException(status_code=409, detail="Wait for this run to finish before making a new version.")
    db.info.update(submission_scope=f"regenerate:{generation_id}:{output_type}", resume_parent=generation_id)
    try:
        return await create_generation(GenerationRequest(
        **await _selection_request(db, original),
        source_id=original.source_id, output_types=[output_type], params=original.params or {},
        budget_type=original.budget_type or "tokens", budget_ceiling=original.budget_ceiling,
        ), db, operator, idempotency_key)
    finally:
        db.info.pop("submission_scope", None)
        db.info.pop("resume_parent", None)



@router.get("/", response_model=list[GenerationResponse])
async def list_generations(
    db: DbSession,
    operator: CurrentOperator,
    limit: int = 50,
) -> list[GenerationResponse]:
    """List recent generations with artifacts."""
    result = await db.execute(
        select(Generation).where(Generation.kind == 'generation').order_by(Generation.created_at.desc()).limit(limit)
    )
    generations = list(result.scalars().all())
    if not generations:
        return []

    gen_ids = [g.id for g in generations]
    source_ids = list({g.source_id for g in generations if g.source_id})

    # Batch load sources and artifacts in 2 queries instead of N+1
    sources_res = await db.execute(select(Source).where(Source.id.in_(source_ids))) if source_ids else None
    sources_map = {s.id: s for s in sources_res.scalars().all()} if sources_res else {}

    artifacts_res = await db.execute(select(Artifact).where(Artifact.generation_id.in_(gen_ids)))
    artifacts_by_gen: dict[UUID, list[Artifact]] = {}
    for a in artifacts_res.scalars().all():
        if a.generation_id:
            artifacts_by_gen.setdefault(a.generation_id, []).append(a)

    responses = []
    for gen in generations:
        try:
            await _check_version_owner(db, gen.id, operator)
            source = await load_context(db, gen) if gen.synthesis else sources_map.get(gen.source_id)
        except (HTTPException, SourceUnavailable):
            continue
        artifacts = artifacts_by_gen.get(gen.id, [])
        responses.append(_build_generation_response(gen, artifacts, source, {}))
    return responses


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/generations/{id}
# ─────────────────────────────────────────────────────────────────

@router.get("/{generation_id}", response_model=GenerationResponse)
async def get_generation(
    generation_id: str,
    db: DbSession,
    operator: CurrentOperator,
) -> GenerationResponse:
    """§3.11 — Get a Generation and its current artifacts. Reflects live async status."""
    try:
        gen_uuid = UUID(generation_id) if not isinstance(generation_id, UUID) else generation_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found.",
        )
    await _check_version_owner(db, gen_uuid, operator)
    generation = await db.get(Generation, gen_uuid)
    if generation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found.",
        )

    source = await load_context(db, generation)

    result = await db.execute(
        select(Artifact).where(Artifact.generation_id == gen_uuid)
    )
    artifacts = list(result.scalars().all())

    # Load overrides if any
    overrides_res = await db.execute(
        select(ComplianceOverride).where(
            ComplianceOverride.artifact_id.in_([a.id for a in artifacts]) if artifacts else False
        )
    )
    overrides_map = {o.artifact_id: o for o in overrides_res.scalars().all()}

    logger.info(
        "GET /generations/%s: returning %d artifacts from DB (target_types=%s status=%s)",
        generation_id, len(artifacts), generation.output_types, getattr(generation.status, "value", generation.status),
    )

    return _build_generation_response(generation, artifacts, source, overrides_map)


@router.get("/{generation_id}/status")
async def get_generation_status(
    generation_id: str,
    db: DbSession,
    operator: CurrentOperator,
) -> dict:
    """Live pipeline stage progress for a generation."""
    try:
        gen_uuid = UUID(generation_id) if not isinstance(generation_id, UUID) else generation_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found.",
        )
    await _check_version_owner(db, gen_uuid, operator)
    generation = await db.get(Generation, gen_uuid)
    if generation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found.",
        )

    from orchestrator.progress import read_progress
    await load_context(db, generation)
    result = await read_progress(db, generation)
    from orchestrator.queue import job_summary
    result["job"] = await job_summary(db, gen_uuid)
    if result["job"] and result["job"]["message"]:
        result["error"] = result["job"]["message"] if generation.status in (GenerationStatus.FAILED, GenerationStatus.CANCELLED) else result["error"]
    return result


@router.post("/{generation_id}/cancel")
async def cancel_generation(generation_id: UUID, db: DbSession, operator: CurrentOperator):
    from sqlalchemy import update
    from orchestrator.runtime import utcnow
    await _check_version_owner(db, generation_id, operator)
    job = await db.get(DurableJob, generation_id)
    if not job:
        raise HTTPException(status_code=409, detail="This earlier run has no durable job to cancel.")
    if job.status not in ("queued", "running"):
        return {"status": job.status, "message": "This run is already finished."}
    updated = await db.execute(update(DurableJob).where(DurableJob.generation_id == generation_id,
        DurableJob.status.in_(["queued", "running"])).values(cancel_requested=True,
        message="Cancellation requested. Provider calls already submitted may still be billed."))
    if updated.rowcount:
        await db.refresh(job)
        if job.status == "queued":
            job.status, job.finished_at = "cancelled", utcnow()
            job.message = "Cancelled. Existing outputs are kept. Submitted provider requests may still be billed."
            generation = await db.get(Generation, generation_id)
            generation.status = GenerationStatus.CANCELLED
        await db.commit()
    return {"status": job.status, "cancel_requested": True,
            "message": "Cancellation requested. Existing outputs are kept."}


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/generations/{id}/artifacts/{type}
# ─────────────────────────────────────────────────────────────────

@router.get("/{generation_id}/artifacts/{output_type}", response_model=ArtifactResponse)
async def get_artifact(
    generation_id: UUID,
    output_type: str,
    db: DbSession,
    operator: CurrentOperator,
) -> ArtifactResponse:
    """§3.7 / §3.11 — Get a single artifact with full explainability data."""
    await _check_version_owner(db, generation_id, operator)
    generation = await db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found.",
        )

    result = await db.execute(
        select(Artifact).where(
            Artifact.generation_id == generation_id,
            Artifact.output_type == output_type,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{output_type}' not found for generation {generation_id}.",
        )

    source = await load_context(db, generation)
    override_res = await db.execute(
        select(ComplianceOverride).where(ComplianceOverride.artifact_id == artifact.id)
    )
    override = override_res.scalar_one_or_none()

    return _artifact_to_response(artifact, generation, source, override)


# ─────────────────────────────────────────────────────────────────
# POST /api/v1/generations/{id}/artifacts/{type}/feedback
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/{generation_id}/artifacts/{output_type}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_feedback(
    generation_id: UUID,
    output_type: str,
    request: FeedbackRequest,
    db: DbSession,
    operator: CurrentOperator,
) -> FeedbackResponse:
    """
    §3.9 — Submit human feedback on an artifact, tagged with complete version metadata.
    """
    await _check_version_owner(db, generation_id, operator)
    generation = await db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found.",
        )

    result = await db.execute(
        select(Artifact).where(
            Artifact.generation_id == generation_id,
            Artifact.output_type == output_type,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{output_type}' not found for generation {generation_id}.",
        )

    from evidence.validation import version
    if request.expected_content_version and request.expected_content_version != version(artifact.content):
        raise HTTPException(409, 'The output changed. Reload it before saving feedback.')
    feedback_payload = {
        "rating": request.rating,
        "comment": request.comment,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "artifact_version": f"{artifact.id}@{version(artifact.content)}",
        "output_type": output_type,
        "prompt_version": generation.prompt_version,
        "model_version": generation.model_version,
        "operator_id": operator,
    }

    artifact.feedback = feedback_payload
    from db.models import AuditRecord
    feedback_payload['content_version'] = version(artifact.content)
    db.add(AuditRecord(event_type='USER_FEEDBACK', operator_id=operator,
                       resource_id=str(artifact.id), metadata_json=feedback_payload))
    await db.commit()
    await db.refresh(artifact)

    logger.info("Feedback saved for generation %s artifact %s", generation_id, output_type)
    return FeedbackResponse(artifact_id=artifact.id, feedback=artifact.feedback)


# ─────────────────────────────────────────────────────────────────
# POST /api/v1/generations/{id}/artifacts/{type}/rerun
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/{generation_id}/artifacts/{output_type}/rerun",
    response_model=RerunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rerun_artifact(
    generation_id: UUID,
    output_type: str,
    request: RerunRequest,
    db: DbSession,
    operator: CurrentOperator,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> RerunResponse:
    """
    §4 — Rerun a skipped or failed artifact under a fresh budget allocation.
    """
    await _check_version_owner(db, generation_id, operator)
    generation = await db.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found.",
        )

    if output_type not in (generation.output_types or []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Output type '{output_type}' is not part of generation {generation_id}.",
        )

    db.info.update(submission_scope=f"rerun:{generation_id}:{output_type}", resume_parent=generation_id)
    try:
        accepted = await create_generation(GenerationRequest(**await _selection_request(db, generation), source_id=generation.source_id,
            output_types=[output_type], params=generation.params or {}, budget_type=request.budget_type,
            budget_ceiling=request.budget_ceiling), db, operator, idempotency_key)
    finally:
        db.info.pop("submission_scope", None)
        db.info.pop("resume_parent", None)
    return RerunResponse(generation_id=accepted.id, output_type=output_type,
        status=accepted.status, message="A new durable run was queued with a fresh budget; original outputs are preserved.")



# ─────────────────────────────────────────────────────────────────
# POST /api/v1/generations/{id}/artifacts/{type}/override
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/{generation_id}/artifacts/{output_type}/override",
    response_model=ComplianceOverrideResponse,
    status_code=status.HTTP_200_OK,
)
async def override_compliance_failure(
    generation_id: UUID,
    output_type: str,
    request: ComplianceOverrideRequest,
    db: DbSession,
    operator: ReviewOperator,
) -> ComplianceOverrideResponse:
    """
    §3.10 / §7 — Audit-logged compliance override for an artifact.
    """
    await _check_version_owner(db, generation_id, operator)
    generation = await db.get(Generation, generation_id)
    if generation: await load_context(db, generation)
    result = await db.execute(
        select(Artifact).where(
            Artifact.generation_id == generation_id,
            Artifact.output_type == output_type,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{output_type}' not found for generation {generation_id}.",
        )

    from evidence.validation import version
    from db.models import AuditRecord
    content_version = version(artifact.content)
    if request.expected_content_version and request.expected_content_version != content_version:
        raise HTTPException(409, 'The output changed. Reload its checks before making a decision.')
    if not any(r.get('reviewer_name') == 'compliance_reviewer' and r.get('passed') is False
               for r in artifact.review_results or [] if isinstance(r, dict)):
        raise HTTPException(409, 'A recorded failed compliance check is required for an exception.')
    override = ComplianceOverride(
        artifact_id=artifact.id,
        operator_id=operator,
        reason=request.reason,
        content_version=content_version,
    )
    db.add(override)
    if artifact.review_status == ArtifactReviewStatus.PASSED:
        artifact.review_status = ArtifactReviewStatus.FAILED
    # A human exception never certifies the model output or erases failed checks.
    db.add(AuditRecord(event_type='COMPLIANCE_OVERRIDE', operator_id=operator,
                      resource_id=str(artifact.id), metadata_json={
                          'reason': request.reason, 'content_version': content_version,
                          'review_results': artifact.review_results, 'decision': 'overridden'}))

    await db.commit()
    await db.refresh(override)

    logger.info(
        "Compliance override applied for artifact=%s operator=%s reason=%s",
        artifact.id, operator, request.reason,
    )

    return ComplianceOverrideResponse(
        artifact_id=artifact.id,
        operator_id=override.operator_id,
        reason=override.reason,
        review_status=artifact.review_status,
        created_at=override.created_at or datetime.now(timezone.utc),
    )


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/history
# ─────────────────────────────────────────────────────────────────

@router.get("/history/list", response_model=HistoryResponse, tags=["history"])
async def list_history(
    db: DbSession,
    operator: CurrentOperator,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by generation status: queued, running, completed, partial_failure, failed",
    ),
    output_type: str | None = Query(
        default=None,
        description="Filter generations that include this output type (e.g. 'linkedin_post')",
    ),
    from_date: str | None = Query(
        default=None,
        description="ISO 8601 datetime — only return generations created at or after this timestamp",
    ),
    to_date: str | None = Query(
        default=None,
        description="ISO 8601 datetime — only return generations created before or at this timestamp",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> HistoryResponse:
    """§3.11 — List Generation history with optional filters."""
    if status_filter is not None:
        try:
            GenerationStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid status '{status_filter}'. "
                    f"Valid values: {[s.value for s in GenerationStatus]}"
                ),
            )

    parsed_from_date: datetime | None = None
    parsed_to_date: datetime | None = None

    if from_date is not None:
        try:
            parsed_from_date = _parse_date(from_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid from_date '{from_date}'. Use ISO 8601 format.",
            )

    if to_date is not None:
        try:
            parsed_to_date = _parse_date(to_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid to_date '{to_date}'. Use ISO 8601 format.",
            )

    if parsed_from_date and parsed_to_date and parsed_from_date > parsed_to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date must be before or equal to to_date.",
        )

    stmt = select(Generation).where(Generation.kind == 'generation').order_by(Generation.created_at.desc())

    if status_filter is not None:
        stmt = stmt.where(Generation.status == GenerationStatus(status_filter))

    if parsed_from_date is not None:
        stmt = stmt.where(Generation.created_at >= parsed_from_date)

    if parsed_to_date is not None:
        stmt = stmt.where(Generation.created_at <= parsed_to_date)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    generations = list(result.scalars().all())

    if output_type is not None:
        generations = [g for g in generations if output_type in (g.output_types or [])]

    items = []
    for g in generations:
        try:
            await _check_version_owner(db, g.id, operator)
            items.append(_build_generation_response(g, [], await load_context(db, g)))
        except (HTTPException, SourceUnavailable):
            continue
    return HistoryResponse(
        items=items,
        total=len(items),
        offset=offset,
        limit=limit,
    )


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> datetime:
    """Parse an ISO 8601 date/datetime string into a timezone-aware datetime."""
    s = date_str.strip()
    import re as _re
    s = _re.sub(r"(\d)([ ])(\d{2}:\d{2})$", r"\1+\3", s)
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(
            f"Cannot parse date string '{date_str}'. Use ISO 8601 format."
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _resolve_source_filename(source: Source | None) -> str:
    """Resolve a clean, human-readable document filename."""
    if not source:
        return "Source_Document.pdf"

    if source.filename:
        return source.filename
    raw_ref = source.raw_content_ref
    if raw_ref:
        raw_name = Path(raw_ref).name
        # If it has format 'Name_hash.ext' -> 'Name.ext'
        match = re.match(r"^(.+)_[0-9a-f]{8}(\.[a-zA-Z0-9]+)$", raw_name)
        if match:
            return f"{match.group(1)}{match.group(2)}"
        # If it is not a pure UUID
        if not re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", raw_name, re.IGNORECASE):
            return raw_name

    # Derive title from first meaningful heading in extracted text if available
    if source.extracted_text:
        for line in source.extracted_text.splitlines()[:5]:
            cleaned = re.sub(r'^[#*\-•\d.]+\s*', '', line).strip()
            if 4 <= len(cleaned) <= 60 and not cleaned.startswith("http"):
                safe_title = re.sub(r'[^\w\s-]', '', cleaned).strip().replace(" ", "_")
                if safe_title:
                    return f"{safe_title}.pdf"

    return "Source_Intelligence_Brief.pdf"


def _build_generation_response(
    generation: Generation,
    artifacts: list[Artifact],
    source: Source | None = None,
    overrides_map: dict[UUID, ComplianceOverride] | None = None,
) -> GenerationResponse:
    skipped = [
        a.output_type for a in artifacts if a.review_status == ArtifactReviewStatus.BUDGET_EXCEEDED
    ]
    overrides = overrides_map or {}
    return GenerationResponse(
        id=generation.id,
        source_id=generation.source_id,
        source_filename=_resolve_source_filename(source),
        source_documents=getattr(source, 'source_documents', []),
        source_conflicts=(generation.synthesis or {}).get('conflicts', []),
        sensitivity=(getattr(source.sensitivity, "value", source.sensitivity) if source else None),
        output_types=generation.output_types,
        status=generation.status,
        pipeline_stage=generation.status.value if hasattr(generation.status, "value") else str(generation.status),
        prompt_version=generation.prompt_version,
        model_version=generation.model_version,
        reviewer_version=generation.reviewer_version,
        budget_type=generation.budget_type or "tokens",
        budget_ceiling=generation.budget_ceiling,
        budget_used=generation.budget_used or 0.0,
        total_tokens=generation.total_tokens or 0,
        total_cost_usd=generation.total_cost_usd or 0.0,
        rerun_count=generation.rerun_count or 0,
        skipped_output_types=skipped,
        artifacts=[_artifact_to_response(a, generation, source, overrides.get(a.id)) for a in artifacts],
        created_at=generation.created_at.isoformat() if hasattr(generation.created_at, "isoformat") else str(generation.created_at or ""),
    )


def _artifact_to_response(
    artifact: Artifact,
    generation: Generation | None = None,
    source: Source | None = None,
    override: ComplianceOverride | None = None,
) -> ArtifactResponse:
    override_dict = None
    if override:
        override_dict = {
            "reason": override.reason,
            "operator_id": override.operator_id,
            "created_at": override.created_at.isoformat() if override.created_at else None,
            'content_version': override.content_version,
        }

    sens_val = source.sensitivity.value if source and hasattr(source.sensitivity, "value") else (source.sensitivity if source else None)
    sens_src = source.sensitivity_source.value if source and hasattr(source.sensitivity_source, "value") else (source.sensitivity_source if source else None)
    sens_conf = source.sensitivity_confidence if source else None

    # Unpack Phase X metadata from review_results if present
    traceform_meta = {}
    cleaned_review_results = []
    for r in (artifact.review_results or []):
        if isinstance(r, dict) and "_traceform_meta" in r:
            traceform_meta = r["_traceform_meta"]
        else:
            cleaned_review_results.append(r)

    from agents.generators.blueprints import get_blueprint
    bp = get_blueprint(artifact.output_type)

    key_insights = traceform_meta.get("key_insights") or []
    blueprint_version = traceform_meta.get("blueprint_version") or bp.blueprint_version_tag
    purpose = traceform_meta.get("purpose") or bp.purpose
    target_audience = traceform_meta.get("target_audience") or bp.audience
    decision_focus = traceform_meta.get("decision_focus") or bp.decision_focus
    quality_score = traceform_meta.get("quality_score")
    quality_breakdown = traceform_meta.get("quality_breakdown")
    format_meta = traceform_meta.get("format_meta") or {}
    role = traceform_meta.get("role") or bp.role
    audience = traceform_meta.get("audience") or bp.audience
    writing_style = traceform_meta.get("writing_style") or bp.writing_style
    differentiation_score = traceform_meta.get("differentiation_score", traceform_meta.get("uniqueness_score"))
    uniqueness_score = traceform_meta.get("uniqueness_score", differentiation_score)
    is_generic = traceform_meta.get("is_generic")
    if not traceform_meta.get("differentiation_measured"):
        differentiation_score = uniqueness_score = is_generic = None

    from evidence.validation import validate_evidence, assurance, version
    from synthesis.context import evidence_text
    evidence = validate_evidence(artifact.content, artifact.facts_used,
        evidence_text(source), source.id if source else None, cleaned_review_results)
    current_override = bool(override and override.content_version == version(artifact.content))
    if override_dict is not None:
        override_dict['applies_to_current_content'] = current_override
    review_attempts = next((r['_review_attempts'] for r in artifact.review_results or []
                           if isinstance(r, dict) and '_review_attempts' in r), [])

    return ArtifactResponse(
        id=artifact.id,
        generation_id=artifact.generation_id,
        output_type=artifact.output_type,
        content=artifact.content,
        review_status=artifact.review_status,
        review_results=cleaned_review_results,
        facts_used=artifact.facts_used,
        cost=artifact.cost,
        feedback=artifact.feedback,
        retry_count=artifact.retry_count or 0,
        counted_as_eval_failure=artifact.counted_as_eval_failure or False,
        rendered_file_ref=artifact.rendered_file_ref,
        prompt_version=generation.prompt_version if generation else None,
        model_version=generation.model_version if generation else None,
        reviewer_version=generation.reviewer_version if generation else None,
        sensitivity=sens_val,
        sensitivity_source=sens_src,
        sensitivity_confidence=sens_conf,
        compliance_override=override_dict,
        evidence=evidence,
        assurance_status=assurance(evidence, cleaned_review_results, current_override),
        review_attempts=review_attempts,
        # Phase X
        key_insights=key_insights,
        blueprint_version=blueprint_version,
        purpose=purpose,
        target_audience=target_audience,
        decision_focus=decision_focus,
        quality_score=quality_score,
        quality_breakdown=quality_breakdown,
        format_meta=format_meta,
        role=role,
        audience=audience,
        writing_style=writing_style,
        differentiation_score=differentiation_score,
        uniqueness_score=uniqueness_score,
        is_generic=is_generic,
    )
