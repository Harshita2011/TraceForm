"""
# §3.8 / §6J — Evaluation API Routes.
"""

import asyncio
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentOperator, get_db
from db.models import EvaluationRun

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluations", tags=["evaluations"])


class EvaluationRunResponse(BaseModel):
    measurement_provenance: str = "not_recorded"
    id: str
    dataset_version: str
    dataset_size: int = Field(..., description="Sample size — mandatory with all accuracy figures (§3.8, §10)")
    fact_accuracy: Optional[float] = None
    hallucination_rate: Optional[float] = None
    citation_coverage: Optional[float] = None
    style_adherence_rate: Optional[float] = None
    avg_latency: Optional[float] = None
    avg_cost: Optional[float] = None
    dataset_size_caption: str = ""
    created_at: str


class EvaluationRunRequest(BaseModel):
    dataset_version: str = "v1"
    dry_run: bool = False


def _evaluation_response(record: EvaluationRun) -> EvaluationRunResponse:
    if not record.dataset_size or record.dataset_size <= 0:
        raise HTTPException(status_code=422, detail="An evaluation requires a recorded sample size.")
    return EvaluationRunResponse(
        id=str(record.id), dataset_version=record.dataset_version, dataset_size=record.dataset_size,
        fact_accuracy=record.fact_accuracy, style_adherence_rate=record.style_adherence_rate,
        # These measurements are not persisted by the current evaluator. Do not infer them.
        hallucination_rate=None, citation_coverage=None,
        avg_latency=record.avg_latency, avg_cost=record.avg_cost,
        dataset_size_caption=f"Evaluated on {record.dataset_size} samples ({record.dataset_version})",
        created_at=record.created_at.isoformat(),
    )


@router.get("/latest", response_model=EvaluationRunResponse | None)
async def get_latest_evaluation(operator: CurrentOperator, db: AsyncSession = Depends(get_db)):
    latest = (await db.execute(select(EvaluationRun).order_by(desc(EvaluationRun.created_at)).limit(1))).scalar_one_or_none()
    return _evaluation_response(latest) if latest else None


@router.get("/history", response_model=List[EvaluationRunResponse])
async def get_evaluation_history(operator: CurrentOperator, db: AsyncSession = Depends(get_db),
                                 limit: int = Query(20, ge=1, le=100)):
    records = (await db.execute(select(EvaluationRun).order_by(desc(EvaluationRun.created_at)).limit(limit))).scalars().all()
    return [_evaluation_response(record) for record in records]


@router.post("/run", status_code=410)
async def trigger_evaluation_run(request: EvaluationRunRequest, operator: CurrentOperator):
    raise HTTPException(410, 'Create a versioned dataset and submit /evaluations/execute. Legacy background evaluation is retired.')
