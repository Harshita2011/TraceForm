"""
# §3.2 Knowledge Extraction Layer — Pydantic v2 schemas for structured knowledge.
# These schemas define the FIXED output shape of the Analyst Agent.
# Generators receive ONLY this structure — never raw source text.
"""

from typing import Literal
from pydantic import BaseModel, Field

from schemas.enums import SensitivityLevel


class Entities(BaseModel):
    """§3.2 — Named entities extracted from a source document."""
    organizations: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    """
    §3.2 / §1.3 — A single verifiable claim extracted from a source.

    source_span MUST be the verbatim text slice from extracted_text.
    start_char and end_char MUST be exact character offsets into extracted_text.
    This is the traceability mechanism the whole product is built on (§1.3, §3.7).
    """
    claim: str
    source_span: str
    start_char: int = Field(ge=0, description="Inclusive start char offset into extracted_text")
    end_char: int = Field(ge=0, description="Exclusive end char offset into extracted_text")
    confidence: float = Field(ge=0.0, le=1.0)
    anchor_resolution: Literal['exact', 'unique_quote'] = 'exact'
    model_start_char: int | None = None
    model_end_char: int | None = None
    fact_key: str | None = None
    source_id: str | None = None
    source_version: str | None = None
    anchors: list[dict] = Field(default_factory=list)


class Relationship(BaseModel):
    """§3.2 — A directional relationship between two entities."""
    source: str
    relation: str
    target: str


class KnowledgeExtraction(BaseModel):
    """
    §3.2 — The canonical output of the Analyst Agent.
    Validates against this schema using Pydantic; LLM output that fails validation
    triggers one retry, then a hard failure (no silent coercion).
    """
    summary: str
    entities: Entities
    facts: list[Fact]
    relationships: list[Relationship]
    domain: str
    source_tone: str
    sensitivity: SensitivityLevel
    sensitivity_source: Literal["operator", "classifier"]
    sensitivity_confidence: float = Field(ge=0.0, le=1.0)
    source_documents: list[dict] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
