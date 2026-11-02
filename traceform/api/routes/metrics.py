"""
# §3.11 System Metrics Endpoint
# Computes system-wide aggregate statistics from database records.
"""

import logging
from fastapi import APIRouter
from sqlalchemy import func, select

from api.dependencies import CurrentOperator, DbSession
from db.models import Artifact, Generation
from schemas.enums import ArtifactReviewStatus, GenerationStatus
from schemas.generation import MetricsResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsResponse)
async def get_system_metrics(
    db: DbSession,
    operator: CurrentOperator,
) -> MetricsResponse:
    """§3.11 — Get aggregate system metrics."""
    # 1. Total Generations
    gen_count_res = await db.execute(select(func.count(Generation.id)).where(Generation.kind == 'generation'))
    total_generations = gen_count_res.scalar() or 0

    # 2. Total Artifacts
    art_count_res = await db.execute(select(func.count(Artifact.id)))
    total_artifacts = art_count_res.scalar() or 0

    # 3. Passed / Failed / Budget Exceeded Artifact counts
    passed_res = await db.execute(
        select(func.count(Artifact.id)).where(Artifact.review_status == ArtifactReviewStatus.PASSED)
    )
    passed_count = passed_res.scalar() or 0

    failed_res = await db.execute(
        select(func.count(Artifact.id)).where(Artifact.review_status == ArtifactReviewStatus.FAILED)
    )
    failed_count = failed_res.scalar() or 0

    budget_exceeded_res = await db.execute(
        select(func.count(Artifact.id)).where(Artifact.review_status == ArtifactReviewStatus.BUDGET_EXCEEDED)
    )
    budget_exceeded_count = budget_exceeded_res.scalar() or 0

    # 4. Rerun counts
    rerun_res = await db.execute(select(func.sum(Generation.rerun_count)))
    total_reruns = rerun_res.scalar() or 0

    # 5. Token & Cost totals
    tokens_res = await db.execute(select(func.sum(Generation.total_tokens)))
    total_tokens = tokens_res.scalar() or 0

    cost_res = await db.execute(select(func.sum(Generation.total_cost_usd)))
    total_cost = cost_res.scalar() or 0.0

    # Calculated rates
    success_rate = round(passed_count / max(total_artifacts, 1), 4) if total_artifacts > 0 else None
    rejection_rate = round(failed_count / max(total_artifacts, 1), 4) if total_artifacts > 0 else None
    generation_cost = await db.scalar(select(func.sum(Generation.total_cost_usd)).where(Generation.kind == 'generation')) or 0
    avg_cost_gen = round(generation_cost / max(total_generations, 1), 6) if total_generations > 0 else None
    avg_cost_art = round(generation_cost / max(total_artifacts, 1), 6) if total_artifacts > 0 else None

    return MetricsResponse(
        total_generations=total_generations,
        total_artifacts=total_artifacts,
        artifact_success_rate=success_rate,
        reviewer_rejection_rate=rejection_rate,
        rerun_count=int(total_reruns),
        budget_exceeded_count=budget_exceeded_count,
        average_cost_per_generation=avg_cost_gen,
        average_cost_per_artifact=avg_cost_art,
        total_tokens_used=int(total_tokens),
        total_cost_usd=round(float(total_cost), 6),
    )
