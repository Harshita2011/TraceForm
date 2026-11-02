from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class DraftSave(BaseModel):
    content: str = Field(max_length=200000)
    expected_revision: int = Field(ge=0)
    base_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    request_id: UUID


class Snapshot(BaseModel):
    source: Literal['draft', 'original', 'import', 'recovery'] = 'draft'
    expected_revision: int = Field(default=0, ge=0)
    content: str | None = Field(default=None, max_length=200000)
    label: str = Field(default='Saved version', min_length=1, max_length=120)
    request_id: UUID


class Restore(BaseModel):
    expected_revision: int = Field(ge=0)
    request_id: UUID


class VersionTask(BaseModel):
    operation: Literal['review', 'full', 'section']
    notes: str = Field(default='', max_length=4000)
    section_id: str | None = Field(default=None, max_length=24)
    budget_type: Literal['tokens', 'cost_usd'] = 'tokens'
    budget_ceiling: float = Field(gt=0, allow_inf_nan=False)
    request_id: UUID
