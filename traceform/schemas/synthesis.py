from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class CollectionWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_ids: list[UUID] = Field(min_length=1, max_length=8)
    expected_revision: int | None = Field(default=None, ge=1)


class AnalyzeSources(BaseModel):
    source_ids: list[UUID] = Field(min_length=2, max_length=8)
    budget_type: Literal['tokens', 'cost_usd'] = 'tokens'
    budget_ceiling: float = Field(gt=0, allow_inf_nan=False)
    request_id: UUID


class ConflictResolution(BaseModel):
    choice: Literal['preserve', 'omit', 'prefer'] = 'preserve'
    preferred_source_id: UUID | None = None
