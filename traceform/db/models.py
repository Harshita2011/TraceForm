"""
# §5 Data Model — SQLAlchemy 2.0 async models for all TraceForm entities.
# Every model has a docstring citing the PRD section it implements.
"""

import enum
import uuid
from datetime import datetime, timezone, timedelta
from threading import Lock

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, relationship

from schemas.enums import (
    ArtifactReviewStatus,
    GenerationStatus,
    SensitivityLevel,
    SensitivitySource,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all TraceForm models."""
    workspace_id = Column(String(36), nullable=False, default='legacy', server_default='legacy', index=True)


class Source(Base):
    """
    §3.1 Source Ingestion Layer — represents an ingested source document.

    raw_content_ref: path in object storage (local disk for now, S3-compatible later).
    sensitivity_source distinguishes operator-set vs. classifier-suggested labels — never conflate them.
    """
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_content_ref = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    extraction_method = Column(String, nullable=True)
    was_truncated = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    extracted_text = Column(Text, nullable=False)
    sensitivity = Column(SAEnum(SensitivityLevel), nullable=False)
    sensitivity_source = Column(SAEnum(SensitivitySource), nullable=False)
    sensitivity_confidence = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    knowledge_extractions = relationship("KnowledgeExtractionModel", back_populates="source")
    generations = relationship("Generation", back_populates="source")


class KnowledgeExtractionModel(Base):
    """
    §3.2 Knowledge Extraction Layer — structured facts extracted from a Source.
    Persisted after the Analyst Agent validates its output against the KnowledgeExtraction schema.
    """
    __tablename__ = "knowledge_extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    summary = Column(Text, nullable=False)
    entities = Column(JSON, nullable=False)       # {organizations, people, locations, products}
    facts = Column(JSON, nullable=False)          # [{claim, source_span, start_char, end_char, confidence}]
    relationships = Column(JSON, nullable=False)  # [{source, relation, target}]
    domain = Column(String, nullable=True)
    source_tone = Column(String, nullable=True)
    conflicts = Column(JSON, nullable=True)
    source_documents = Column(JSON, nullable=True)

    source = relationship("Source", back_populates="knowledge_extractions")


class Generation(Base):
    """
    §5 Data Model — a Generation job requesting one or more output artifacts.
    prompt_version/model_version/reviewer_version are pinned at creation time for reproducibility (§3.5, §4).
    """
    __tablename__ = "generations"
    kind = Column(String, nullable=False, default='generation', server_default='generation')
    synthesis = Column(JSON, nullable=True)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    output_types = Column(JSON, nullable=False)   # list[str]
    params = Column(JSON, nullable=False)         # GenerationParams dict
    prompt_version = Column(String, nullable=True)
    reviewer_version = Column(String, nullable=True, default="unset")  # Phase 3
    model_version = Column(String, nullable=True)
    status = Column(SAEnum(GenerationStatus), nullable=False, default=GenerationStatus.PENDING)

    budget_type = Column(String, nullable=False, default="tokens")  # "tokens" | "cost_usd"
    budget_ceiling = Column(Float, nullable=True)
    budget_used = Column(Float, nullable=False, default=0.0)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(Float, nullable=False, default=0.0)
    rerun_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source = relationship("Source", back_populates="generations")
    artifacts = relationship("Artifact", back_populates="generation")



_event_clock_lock = Lock()
_last_event_time = datetime.min.replace(tzinfo=timezone.utc)


def _event_time():
    """Windows can return the same clock tick for consecutive transitions."""
    global _last_event_time
    with _event_clock_lock:
        now = datetime.now(timezone.utc)
        _last_event_time = max(now, _last_event_time + timedelta(microseconds=1))
        return _last_event_time


class PipelineEvent(Base):
    """Durable stage transitions, including per-output progress and safe failure guidance."""
    __tablename__ = "pipeline_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(UUID(as_uuid=True), ForeignKey("generations.id"), nullable=False, index=True)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False)
    output_type = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)


class ProviderConfiguration(Base):
    """Immutable encrypted provider/pricing snapshot; jobs retain the revision they started with."""
    __tablename__ = "provider_configurations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    encrypted_key = Column(Text, nullable=True)
    pricing = Column(JSON, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)


class ActiveProvider(Base):
    __tablename__ = "active_provider"
    id = Column(Integer, primary_key=True)
    configuration_id = Column(UUID(as_uuid=True), ForeignKey("provider_configurations.id"), nullable=False)
    revision = Column(Integer, nullable=False, default=1)


class DurableJob(Base):
    __tablename__ = "durable_jobs"
    task_kind = Column(String, nullable=False, default='generation', server_default='generation')
    generation_id = Column(UUID(as_uuid=True), ForeignKey("generations.id"), primary_key=True)
    configuration_id = Column(UUID(as_uuid=True), ForeignKey("provider_configurations.id"), nullable=False)
    status = Column(String, nullable=False, default="queued", index=True)
    worker_id = Column(String, nullable=True)
    lease_token = Column(String, nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    reserved_budget = Column(Float, nullable=False, default=0)
    message = Column(Text, nullable=True)
    parent_generation_id = Column(UUID(as_uuid=True), nullable=True)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_extractions.id"), nullable=True)
    extraction_fingerprint = Column(String, nullable=True)
    extraction_reused = Column(Boolean, nullable=False, default=False)
    plan_fingerprint = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class JobRequest(Base):
    __tablename__ = "job_requests"
    key_hash = Column(String, primary_key=True)
    payload_hash = Column(String, nullable=False)
    generation_id = Column(UUID(as_uuid=True), ForeignKey("generations.id"), nullable=False)


class CreationPreset(Base):
    __tablename__ = "creation_presets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    settings = Column(JSON, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)


class WorkerState(Base):
    __tablename__ = "worker_states"
    worker_id = Column(String, primary_key=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)


class LLMCall(Base):
    __tablename__ = "llm_calls"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(UUID(as_uuid=True), ForeignKey("generations.id"), nullable=False, index=True)
    fingerprint = Column(String, nullable=False)
    output_type = Column(String, nullable=True)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False)
    model = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    pricing = Column(JSON, nullable=False)
    reservation = Column(Float, nullable=False)
    response_text = Column(Text, nullable=True)
    usage = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("generation_id", "fingerprint", name="uq_llm_call_fingerprint"),)


class Artifact(Base):
    """
    §5 Data Model — a single generated output artifact produced by a Generator Agent.

    counted_as_eval_failure: set True when a second Fact Review failure occurs (§3.6).
    This flag ensures Phase 5's evaluation harness can include it as a failure without a schema change.
    """
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id = Column(UUID(as_uuid=True), ForeignKey("generations.id"), nullable=False)
    output_type = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    rendered_file_ref = Column(String, nullable=True)
    review_results = Column(JSON, nullable=True)  # list[ReviewResult]
    review_status = Column(SAEnum(ArtifactReviewStatus), nullable=True)
    facts_used = Column(JSON, nullable=True)      # list[Fact] actually used by the generator
    cost = Column(JSON, nullable=True)            # {analyst_share, generation, regeneration, ...}
    feedback = Column(JSON, nullable=True)        # {rating, comment, prompt_version, model_version}
    retry_count = Column(Integer, nullable=False, default=0)
    counted_as_eval_failure = Column(Boolean, nullable=False, default=False)  # §3.6

    generation = relationship("Generation", back_populates="artifacts")
    compliance_overrides = relationship("ComplianceOverride", back_populates="artifact")


class EvaluationRun(Base):
    """
    §3.8 Evaluation Harness — persists aggregate metrics from an eval run.
    dataset_size MUST always accompany accuracy figures — never publish numbers without sample size (§3.8, §10).
    """
    __tablename__ = "evaluation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_version = Column(String, nullable=False)
    dataset_size = Column(Integer, nullable=False)
    fact_accuracy = Column(Float, nullable=True)
    style_adherence_rate = Column(Float, nullable=True)
    avg_latency = Column(Float, nullable=True)
    avg_cost = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ComplianceOverride(Base):
    """
    §3.10 / §7 — Audit log for operator overrides of Compliance hard-gate failures.
    Decisions remain attributed to an exact content version; failed checks remain unchanged.
    """
    __tablename__ = "compliance_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id = Column(UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=False)
    operator_id = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    content_version = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    artifact = relationship("Artifact", back_populates="compliance_overrides")


class AuditRecord(Base):
    """
    §6G / §7 — Unified Governance Audit Log.
    Tracks all lifecycle events (source processing, generations, reviews, overrides, feedback, eval runs).
    """
    __tablename__ = "audit_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String, nullable=False)
    operator_id = Column(String, nullable=False, default="system")
    resource_id = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApiKeyRecord(Base):
    """
    §6F / §7 — Scoped API Key Storage with SHA-256 Hashing.
    """
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String, nullable=False, unique=True)
    operator_id = Column(String, nullable=False)
    role = Column(String, nullable=False, default="analyst")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class ArtifactDraft(Base):
    """Private mutable working copy. Revision is an optimistic concurrency token."""
    __tablename__ = 'artifact_drafts'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id = Column(UUID(as_uuid=True), ForeignKey('artifacts.id'), nullable=False)
    owner = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    base_hash = Column(String(64), nullable=False)
    last_request_id = Column(String(36), nullable=False)
    request_hash = Column(String(64), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)
    __table_args__ = (UniqueConstraint('artifact_id', 'owner', name='uq_artifact_draft_owner'),)


class ArtifactVersion(Base):
    """Immutable content snapshots; review evidence lives in separate immutable rows."""
    __tablename__ = 'artifact_versions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id = Column(UUID(as_uuid=True), ForeignKey('artifacts.id'), nullable=False)
    owner = Column(String, nullable=False)
    label = Column(String(120), nullable=False)
    origin = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    source_hash = Column(String(64), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('artifact_versions.id'), nullable=True)
    request_id = Column(String(128), nullable=False)
    request_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)
    __table_args__ = (UniqueConstraint('artifact_id', 'owner', 'request_id', name='uq_artifact_version_request'),)


class VersionReview(Base):
    __tablename__ = 'version_reviews'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = Column(UUID(as_uuid=True), ForeignKey('artifact_versions.id'), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey('generations.id'), nullable=False, unique=True)
    content_hash = Column(String(64), nullable=False)
    source_hash = Column(String(64), nullable=False)
    policy_hash = Column(String(64), nullable=False)
    results = Column(JSON, nullable=False)
    facts_used = Column(JSON, nullable=False)
    passed = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)


class VersionOperation(Base):
    __tablename__ = 'version_operations'
    job_id = Column(UUID(as_uuid=True), ForeignKey('generations.id'), primary_key=True)
    version_id = Column(UUID(as_uuid=True), ForeignKey('artifact_versions.id'), nullable=False)
    owner = Column(String, nullable=False)
    operation = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    result_version_id = Column(UUID(as_uuid=True), ForeignKey('artifact_versions.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)


class SourceCollection(Base):
    __tablename__ = 'source_collections'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner = Column(String, nullable=False)
    name = Column(String(120), nullable=False)
    source_ids = Column(JSON, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_event_time, nullable=False)


class GenerationDocument(Base):
    """Immutable per-run document selection and evidence text, separate from the live library."""
    __tablename__ = 'generation_documents'
    generation_id = Column(UUID(as_uuid=True), ForeignKey('generations.id'), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey('sources.id'), primary_key=True)
    position = Column(Integer, nullable=False)
    filename = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    source_version = Column(String(64), nullable=False)
    sensitivity = Column(String, nullable=False)
    sensitivity_source = Column(String, nullable=False)
    sensitivity_confidence = Column(Float, nullable=False)


class SynthesisAnalysis(Base):
    __tablename__ = 'synthesis_analyses'
    generation_id = Column(UUID(as_uuid=True), ForeignKey('generations.id'), primary_key=True)
    owner = Column(String, nullable=False)
    manifest_hash = Column(String(64), nullable=False)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey('knowledge_extractions.id'), nullable=True)
    conflicts = Column(JSON, nullable=True)

# Register identity/collaboration tables for fresh-schema creation and migrations.
from teams import models as _team_models
from eval import models as _benchmark_models
