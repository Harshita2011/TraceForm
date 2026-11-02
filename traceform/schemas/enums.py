"""
# §5 Shared Enums — used by both SQLAlchemy models and Pydantic schemas.
# Defining them here prevents circular imports and ensures a single source of truth.
"""

import enum


class SensitivityLevel(str, enum.Enum):
    """§3.1 — Classification levels for source content sensitivity."""
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


class SensitivitySource(str, enum.Enum):
    """§3.1.1 — Provenance of a sensitivity label: operator-set vs. classifier-suggested."""
    OPERATOR = "operator"
    CLASSIFIER = "classifier"


class GenerationStatus(str, enum.Enum):
    """§4 — Lifecycle status of a Generation job."""
    PENDING = "pending"
    QUEUED = "queued"        # Phase 2: Celery-enqueued
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactReviewStatus(str, enum.Enum):
    """§3.5 — Review outcome for a single generated Artifact."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"  # §4 — distinct terminal state, not a silent skip
