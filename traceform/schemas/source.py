"""
# §3.1 Source Ingestion Layer — Pydantic schemas for source ingestion requests and responses.
"""

from uuid import UUID
from pydantic import BaseModel, Field

from schemas.enums import SensitivityLevel, SensitivitySource


class SourceIngestionResponse(BaseModel):
    """Response returned after successfully ingesting a source document."""
    id: UUID
    sensitivity: SensitivityLevel
    sensitivity_source: SensitivitySource
    sensitivity_confidence: float
    extracted_text_length: int
    message: str = "Source ingested successfully"
