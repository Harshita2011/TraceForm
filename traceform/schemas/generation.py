"""
# §3.4 / §3.11 Generation schemas — Pydantic schemas for generation requests and responses.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
from schemas.synthesis import ConflictResolution

from schemas.enums import ArtifactReviewStatus, GenerationStatus


class GenerationParams(BaseModel):
    """§3.4 — Parameters controlling how content is generated."""
    audience: str = Field(default="general", description="Target audience for the content")
    tone: str = Field(default="professional", description="Desired tone of the output")
    language: str = Field(default="en", description="ISO 639-1 language code")
    detail_level: str = Field(default="medium", description="low | medium | high")
    objective: str = Field(default="", description="Primary goal of the content")
    style: str = Field(default="", description="Style guidelines or brand voice notes")
    brand_name: str = Field(default="", max_length=150)
    sections: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, values):
        if any(not v.strip() or len(v) > 100 or "\n" in v or "\r" in v for v in values):
            raise ValueError("Additional section titles must be 1–100 characters on one line")
        return list(dict.fromkeys(v.strip() for v in values))
    output_type: str | None = Field(default=None, description="Current output type context if known")
    overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-output-type param overrides, e.g. {'twitter_post': {'tone': 'punchy'}}"
    )


    def for_output_type(self, output_type: str) -> "GenerationParams":
        """Merge global params with per-output-type overrides. Overrides win."""
        override_data = self.overrides.get(output_type, {})
        merged = self.model_validate({**self.model_dump(), **override_data, "output_type": output_type, "overrides": {}})
        return merged

    @field_validator("overrides")
    @classmethod
    def valid_overrides(cls, values):
        for value in values.values():
            if any(k not in cls.model_fields or k in {"overrides", "output_type"} for k in value):
                raise ValueError("Unsupported output preference override")
            cls.model_validate({**value, "overrides": {}})
        return values



class GenerationRequest(BaseModel):
    """Request body for POST /api/v1/generations."""
    source_id: UUID | None = None
    source_ids: list[UUID] = Field(default_factory=list, max_length=8)
    analysis_id: UUID | None = None
    conflict_resolutions: dict[str, ConflictResolution] = Field(default_factory=dict)
    output_types: list[str] = Field(min_length=1, description="List of output type keys from YAML config")
    params: GenerationParams = Field(default_factory=GenerationParams)
    budget_type: Literal["tokens", "cost_usd"] = Field(default="tokens", description="'tokens' or 'cost_usd'")
    budget_ceiling: float | None = Field(
        default=None, gt=0, allow_inf_nan=False,
        description="Budget cap for this generation (in tokens or USD depending on budget_type)."
    )

    @model_validator(mode='after')
    def source_selection(self):
        if not self.source_id and not self.source_ids:
            raise ValueError('Choose a source document.')
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError('Select each source only once.')
        if self.source_id and self.source_ids and self.source_id != self.source_ids[0]:
            raise ValueError('The primary source must be the first selected source.')
        if len(self.source_ids) > 1 and not self.analysis_id:
            raise ValueError('Analyze the selected sources before generating a combined output.')
        return self


    @field_validator("output_types")
    @classmethod
    def unique_output_types(cls, values: list[str]) -> list[str]:
        import re
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value) for value in values):
            raise ValueError("Choose valid output format keys")
        if len(values) != len(set(values)):
            raise ValueError("Select each output type only once")
        return values


class GenerationAcceptedResponse(BaseModel):
    """
    §3.11 / §4 — Phase 2 202 response for POST /api/v1/generations.
    Returns immediately after enqueueing — poll GET /api/v1/generations/{id} for status.
    """
    id: UUID
    status: GenerationStatus
    prompt_version: str | None
    model_version: str | None
    message: str


class ArtifactResponse(BaseModel):
    """§3.7 / Phase X — Full explainability response shape for a single generated artifact."""
    id: UUID
    generation_id: UUID | None = None
    output_type: str
    content: str | None = None
    review_status: ArtifactReviewStatus | None = None
    review_results: list[dict] | None = None
    facts_used: list[dict] | None = None
    cost: dict | None = None
    feedback: dict | None = None
    retry_count: int = 0
    counted_as_eval_failure: bool = False
    rendered_file_ref: str | None = None
    prompt_version: str | None = None
    model_version: str | None = None
    reviewer_version: str | None = None
    sensitivity: str | None = None
    sensitivity_source: str | None = None
    sensitivity_confidence: float | None = None
    compliance_override: dict | None = None
    evidence: dict | None = None
    assurance_status: str = 'unreviewed'
    review_attempts: list[dict] = Field(default_factory=list)
    # Phase X Extensions
    key_insights: list[str] | None = None
    blueprint_version: str | None = None
    purpose: str | None = None
    target_audience: str | None = None
    decision_focus: str | None = None
    quality_score: float | None = None
    quality_breakdown: dict | None = None
    format_meta: dict | None = None
    role: str | None = None
    audience: str | None = None
    writing_style: str | None = None
    differentiation_score: float | None = None
    uniqueness_score: float | None = None
    is_generic: bool | None = None


class GenerationResponse(BaseModel):
    """Response shape for GET /api/v1/generations/{id}."""
    id: UUID
    source_id: UUID
    source_filename: str | None = None
    source_documents: list[dict] = Field(default_factory=list)
    source_conflicts: list[dict] = Field(default_factory=list)
    sensitivity: str | None = None
    output_types: list[str]
    status: GenerationStatus
    pipeline_stage: str | None = None
    prompt_version: str | None = None
    model_version: str | None = None
    reviewer_version: str | None = None
    budget_type: str = "tokens"
    budget_ceiling: float | None = None
    budget_used: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    rerun_count: int = 0
    skipped_output_types: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactResponse] = Field(default_factory=list)
    created_at: str | datetime | None = None


class HistoryResponse(BaseModel):
    """Response shape for GET /api/v1/history — paginated list of generations."""
    items: list[GenerationResponse]
    total: int
    offset: int
    limit: int


class ComplianceOverrideRequest(BaseModel):
    """§3.10 / §7 — Request body for POST /api/v1/generations/{id}/artifacts/{type}/override."""
    reason: str = Field(min_length=10, max_length=2000, description="Audit-logged justification for a compliance exception")
    expected_content_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    @field_validator('reason')
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 10:
            raise ValueError('Explain the decision in at least 10 characters')
        return value.strip()


class ComplianceOverrideResponse(BaseModel):
    """Response shape for a successful compliance override."""
    artifact_id: UUID
    operator_id: str
    reason: str
    review_status: ArtifactReviewStatus
    created_at: datetime
    decision: Literal['overridden'] = 'overridden'


class FeedbackRequest(BaseModel):
    """§3.9 — Request body for POST /api/v1/generations/{id}/artifacts/{type}/feedback."""
    rating: Literal['positive', 'negative', 'thumbs_up', 'thumbs_down']
    comment: str | None = Field(default=None, max_length=4000)
    expected_content_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class FeedbackResponse(BaseModel):
    """Response shape for feedback submission."""
    artifact_id: UUID
    feedback: dict


class RerunRequest(BaseModel):
    """§4 — Request body for POST /api/v1/generations/{id}/artifacts/{type}/rerun."""
    budget_type: Literal["tokens", "cost_usd"] = Field(default="tokens", description="'tokens' or 'cost_usd'")
    budget_ceiling: float | None = Field(default=None, description="Fresh budget allocation for rerun")


class RerunResponse(BaseModel):
    """Response shape for artifact rerun."""
    generation_id: UUID
    output_type: str
    status: GenerationStatus
    message: str


class MetricsResponse(BaseModel):
    """§3.11 — System-wide aggregate metrics."""
    total_generations: int
    total_artifacts: int
    artifact_success_rate: float | None
    reviewer_rejection_rate: float | None
    rerun_count: int
    budget_exceeded_count: int
    average_cost_per_generation: float | None
    average_cost_per_artifact: float | None
    total_tokens_used: int
    total_cost_usd: float
