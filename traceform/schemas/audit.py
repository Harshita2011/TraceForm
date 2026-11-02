from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    VERSION_SAVED = 'VERSION_SAVED'
    VERSION_RESTORED = 'VERSION_RESTORED'
    VERSION_TASK_STARTED = 'VERSION_TASK_STARTED'
    SOURCE_UPLOADED = "SOURCE_UPLOADED"
    SOURCE_PROCESSED = "SOURCE_PROCESSED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ARTIFACT_GENERATED = "ARTIFACT_GENERATED"
    REVIEW_PASSED = "REVIEW_PASSED"
    REVIEW_FAILED = "REVIEW_FAILED"
    COMPLIANCE_OVERRIDE = "COMPLIANCE_OVERRIDE"
    ARTIFACT_EXPORTED = "ARTIFACT_EXPORTED"
    USER_FEEDBACK = "USER_FEEDBACK"
    EVALUATION_RUN = "EVALUATION_RUN"
    API_KEY_CREATED = "API_KEY_CREATED"
    API_KEY_REVOKED = "API_KEY_REVOKED"


class AuditRecordCreate(BaseModel):
    event_type: AuditEventType
    operator_id: str
    resource_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditRecordResponse(BaseModel):
    id: str
    event_type: str
    operator_id: str
    resource_id: Optional[str] = None
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
