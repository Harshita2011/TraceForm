"""Artifact-ID routes used by the workspace; delegate mutations to the canonical handlers."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from api.dependencies import CurrentOperator, DbSession, ReviewOperator, review_access
from fastapi import Depends
from typing import Annotated
from api.routes.generations import _artifact_to_response, submit_feedback, override_compliance_failure, _check_version_owner
from synthesis.context import load_context
from db.models import Artifact, Generation, Source, ComplianceOverride, AuditRecord
from schemas.generation import ArtifactResponse, FeedbackRequest, FeedbackResponse, ComplianceOverrideRequest, ComplianceOverrideResponse

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


async def _find(db, artifact_id, operator):
    artifact = await db.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    await _check_version_owner(db, artifact.generation_id, operator)
    return artifact


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_by_id(artifact_id: UUID, db: DbSession, operator: CurrentOperator):
    artifact = await _find(db, artifact_id, operator)
    generation = await db.get(Generation, artifact.generation_id)
    source = await load_context(db, generation) if generation else None
    override = (await db.execute(select(ComplianceOverride).where(
        ComplianceOverride.artifact_id == artifact_id).order_by(ComplianceOverride.created_at.desc()))).scalars().first()
    return _artifact_to_response(artifact, generation, source, override)


@router.post("/{artifact_id}/feedback", response_model=FeedbackResponse)
async def feedback_by_id(artifact_id: UUID, request: FeedbackRequest, db: DbSession, operator: CurrentOperator):
    artifact = await _find(db, artifact_id, operator)
    return await submit_feedback(artifact.generation_id, artifact.output_type, request, db, operator)


@router.post("/{artifact_id}/compliance-override", response_model=ComplianceOverrideResponse)
async def override_by_id(artifact_id: UUID, request: ComplianceOverrideRequest, db: DbSession, operator: ReviewOperator):
    artifact = await _find(db, artifact_id, operator)
    return await override_compliance_failure(artifact.generation_id, artifact.output_type, request, db, operator)


@router.get('/{artifact_id}/review-context')
async def review_context(artifact_id: UUID, db: DbSession, operator: CurrentOperator,
                         can_override: Annotated[bool, Depends(review_access)]):
    artifact = await _find(db, artifact_id, operator)
    records = (await db.execute(select(AuditRecord).where(AuditRecord.resource_id == str(artifact.id),
        AuditRecord.event_type.in_(['USER_FEEDBACK', 'COMPLIANCE_OVERRIDE'])).order_by(
        AuditRecord.created_at.desc()).limit(50))).scalars().all()
    return {'can_override': can_override, 'events': [
        {'id': str(r.id), 'event': r.event_type, 'operator': r.operator_id,
         'created_at': r.created_at.isoformat(), 'details': r.metadata_json} for r in records]}
