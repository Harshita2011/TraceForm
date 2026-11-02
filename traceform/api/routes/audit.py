"""
# §6G / §7 — Unified Governance Audit Trail API Route.
"""

import logging
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentOperator, DbSession, get_db
from db.models import AuditRecord, Artifact, Generation
from schemas.audit import AuditEventType, AuditRecordResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


async def log_audit_event(
    db: AsyncSession,
    event_type: AuditEventType,
    operator_id: str,
    resource_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditRecord:
    """Helper to record an immutable governance audit event in the database."""
    record = AuditRecord(
        event_type=event_type.value,
        operator_id=operator_id,
        resource_id=resource_id,
        metadata_json=metadata or {},
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    logger.info("AUDIT EVENT: %s (operator=%s resource=%s)", event_type.value, operator_id, resource_id)
    return record


@router.get("/trail", response_model=List[AuditRecordResponse], status_code=status.HTTP_200_OK)
async def get_audit_trail(
    db: DbSession,
    operator: CurrentOperator,
    event_type: Optional[AuditEventType] = Query(None, description="Filter by event type"),
    operator_id: Optional[str] = Query(None, description="Filter by operator ID"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
) -> List[AuditRecordResponse]:
    """
    §6G — Query the unified audit trail for governance, compliance, and security oversight.
    """
    stmt = select(AuditRecord).order_by(desc(AuditRecord.created_at)).limit(limit)

    if event_type:
        stmt = stmt.where(AuditRecord.event_type == event_type.value)
    if operator_id:
        stmt = stmt.where(AuditRecord.operator_id == operator_id)
    if resource_id:
        stmt = stmt.where(AuditRecord.resource_id == resource_id)

    result = await db.execute(stmt)
    records = result.scalars().all()
    visible = []
    for record in records:
        try:
            identifier = UUID(record.resource_id or '')
        except ValueError:
            visible.append(record); continue
        artifact = await db.get(Artifact, identifier)
        generation = await db.get(Generation, artifact.generation_id if artifact else identifier)
        from teams.scope import team
        if not team() and generation and generation.synthesis and generation.synthesis.get('owner') != operator:
            continue
        visible.append(record)

    return [
        AuditRecordResponse(
            id=str(r.id),
            event_type=r.event_type,
            operator_id=r.operator_id,
            resource_id=r.resource_id,
            timestamp=r.created_at,
            metadata=r.metadata_json or {},
        )
        for r in visible
    ]
