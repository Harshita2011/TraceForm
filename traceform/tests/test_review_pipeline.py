"""
# Phase 3 Pipeline Tests — Fact regeneration loop, second-failure path, compliance hard gate, and override endpoint.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from agents.generators.blueprints import get_blueprint
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agents.base import GeneratorArtifactResult
from db.models import Artifact, ComplianceOverride, Generation, KnowledgeExtractionModel, Source
from schemas.enums import ArtifactReviewStatus, GenerationStatus, SensitivityLevel, SensitivitySource
from schemas.review import ReviewResult


@pytest.fixture
def dummy_task():
    task = MagicMock()
    task.request.retries = 0
    return task


# ─── 1. Fact Reviewer Bounded Single Regeneration ────────────────────────────

class TestFactRegenerationPipeline:
    """§3.6 — Tests for Fact Reviewer single bounded retry and second-failure path."""

    async def test_fact_review_recovery_on_single_regeneration(
        self, db_session: AsyncSession, session_factory, dummy_task
    ):
        """
        Attempt 1 fails fact review -> triggers 1 regeneration with correction_notes ->
        Attempt 2 passes -> Artifact delivered with PASSED, retry_count=1, counted_as_eval_failure=False.
        """
        from orchestrator.jobs import _async_run_generator_task

        # Seed Source, Generation, KE
        source = Source(
            extracted_text="Apple Q3 revenue $85.8B.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.9,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="Apple Q3",
            entities={"organizations": ["Apple"], "people": [], "locations": [], "products": []},
            facts=[{"claim": "Revenue $85.8B", "source_span": "revenue $85.8B", "start_char": 9, "end_char": 23, "confidence": 0.95}],
            relationships=[],
            domain="tech",
            source_tone="neutral",
        )
        db_session.add(ke)
        await db_session.commit()

        call_count = 0

        class _MockGenerator:
            async def generate(self, context, params, correction_notes=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    content = "Apple revenue reached $999B!"
                else:
                    assert correction_notes is not None
                    content = "Apple revenue reached $85.8B."
                return GeneratorArtifactResult(
                    output_type="linkedin_post",
                    content="\n\n".join("## " + title + "\n" + content for title in get_blueprint("linkedin_post").sections),
                    facts_used=[{"claim": content, "source_span": "revenue $85.8B"}],
                    prompt_version="1.0.0",
                    model_version="claude-opus-4-5",
                    token_usage={"input_tokens": 100, "output_tokens": 50},
                )

        # Mock Reviewers
        review_call_count = 0

        class _MockFactReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                nonlocal review_call_count
                review_call_count += 1
                if review_call_count == 1:
                    return ReviewResult(
                        reviewer_name="fact_reviewer",
                        passed=False,
                        details={"failing_claims": ["Apple revenue reached $999B!"]},
                        reviewer_version="1.0.0",
                    )
                return ReviewResult(
                    reviewer_name="fact_reviewer",
                    passed=True,
                    details={"verified_claims": ["Apple revenue reached $85.8B."]},
                    reviewer_version="1.0.0",
                )

        class _MockStyleReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                return ReviewResult(reviewer_name="style_reviewer", passed=True, details={}, reviewer_version="1.0.0")

        class _MockComplianceReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                return ReviewResult(reviewer_name="compliance_reviewer", passed=True, details={}, reviewer_version="1.0.0")

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            with patch("orchestrator.jobs.GenericGeneratorAgent", return_value=_MockGenerator()):
                with patch("orchestrator.jobs.FactReviewer", return_value=_MockFactReviewer()):
                    with patch("orchestrator.jobs.StyleReviewer", return_value=_MockStyleReviewer()):
                        with patch("orchestrator.jobs.ComplianceReviewer", return_value=_MockComplianceReviewer()):
                            await _async_run_generator_task(
                                dummy_task, str(gen.id), str(ke.id), "linkedin_post", "claude-opus-4-5", 0.0
                            )

        res = await db_session.execute(select(Artifact).where(Artifact.generation_id == gen.id))
        artifact = res.scalar_one()

        assert call_count == 2, "Must perform exactly 1 regeneration attempt"
        assert artifact.review_status == ArtifactReviewStatus.PASSED
        assert artifact.retry_count == 1
        assert artifact.counted_as_eval_failure is False
        assert "85.8B" in artifact.content

    async def test_fact_review_second_failure_path(
        self, db_session: AsyncSession, session_factory, dummy_task
    ):
        """
        §3.6 Second-Failure Path:
        Attempt 1 fails -> Attempt 2 also fails ->
        Artifact delivered anyway, review_status=FAILED, retry_count=1,
        counted_as_eval_failure=True, unresolved claims preserved.
        """
        from orchestrator.jobs import _async_run_generator_task

        source = Source(
            extracted_text="Apple Q3 revenue $85.8B.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.9,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="Apple Q3",
            entities={"organizations": ["Apple"], "people": [], "locations": [], "products": []},
            facts=[{"claim": "Revenue $85.8B", "source_span": "revenue $85.8B", "start_char": 9, "end_char": 23, "confidence": 0.95}],
            relationships=[],
            domain="tech",
            source_tone="neutral",
        )
        db_session.add(ke)
        await db_session.commit()

        call_count = 0

        class _PersistentFailingGenerator:
            async def generate(self, context, params, correction_notes=None):
                nonlocal call_count
                call_count += 1
                return GeneratorArtifactResult(
                    output_type="linkedin_post",
                    content="Apple revenue reached $999B!",
                    facts_used=[],
                    prompt_version="1.0.0",
                    model_version="claude-opus-4-5",
                    token_usage={"input_tokens": 100, "output_tokens": 50},
                )

        class _AlwaysFailingFactReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                return ReviewResult(
                    reviewer_name="fact_reviewer",
                    passed=False,
                    details={"failing_claims": ["Apple revenue reached $999B!"]},
                    reviewer_version="1.0.0",
                )

        class _PassReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                return ReviewResult(reviewer_name="ok", passed=True, details={}, reviewer_version="1.0.0")

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            with patch("orchestrator.jobs.GenericGeneratorAgent", return_value=_PersistentFailingGenerator()):
                with patch("orchestrator.jobs.FactReviewer", return_value=_AlwaysFailingFactReviewer()):
                    with patch("orchestrator.jobs.StyleReviewer", return_value=_PassReviewer()):
                        with patch("orchestrator.jobs.ComplianceReviewer", return_value=_PassReviewer()):
                            await _async_run_generator_task(
                                dummy_task, str(gen.id), str(ke.id), "linkedin_post", "claude-opus-4-5", 0.0
                            )

        res = await db_session.execute(select(Artifact).where(Artifact.generation_id == gen.id))
        artifact = res.scalar_one()

        assert call_count == 2, "Must boundedly attempt exactly 1 regeneration (total 2 attempts), never more"
        assert artifact.review_status == ArtifactReviewStatus.FAILED
        assert artifact.retry_count == 1
        assert artifact.counted_as_eval_failure is True
        # Verify failing claim is preserved in review_results
        fact_res = next(r for r in artifact.review_results if r.get("reviewer_name") == "fact_reviewer")
        assert "Apple revenue reached $999B!" in fact_res["details"]["failing_claims"]


# ─── 2. Compliance Hard Gate Pipeline ────────────────────────────────────────

class TestComplianceHardGatePipeline:
    """§3.5c / §7 — Compliance failures hard-fail without auto-retry."""

    async def test_compliance_failure_does_not_auto_regenerate(
        self, db_session: AsyncSession, session_factory, dummy_task
    ):
        """Compliance failure must immediately hard-fail with retry_count=0."""
        from orchestrator.jobs import _async_run_generator_task

        source = Source(
            extracted_text="Secret document.",
            sensitivity=SensitivityLevel.INTERNAL,
            sensitivity_source=SensitivitySource.OPERATOR,
            sensitivity_confidence=1.0,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="Secret",
            entities={"organizations": [], "people": [], "locations": [], "products": []},
            facts=[],
            relationships=[],
            domain="internal",
            source_tone="confidential",
        )
        db_session.add(ke)
        await db_session.commit()

        call_count = 0

        class _MockGenerator:
            async def generate(self, context, params, correction_notes=None):
                nonlocal call_count
                call_count += 1
                return GeneratorArtifactResult(
                    output_type="linkedin_post",
                    content="Public leak of internal secret.",
                    facts_used=[],
                    prompt_version="1.0.0",
                    model_version="claude-opus-4-5",
                    token_usage={"input_tokens": 50, "output_tokens": 20},
                )

        class _FailingComplianceReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                return ReviewResult(
                    reviewer_name="compliance_reviewer",
                    passed=False,
                    details={"violations": ["Sensitivity conflict: internal source to public output"]},
                    reviewer_version="1.0.0",
                )

        class _PassReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                return ReviewResult(reviewer_name="ok", passed=True, details={}, reviewer_version="1.0.0")

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            with patch("orchestrator.jobs.GenericGeneratorAgent", return_value=_MockGenerator()):
                with patch("orchestrator.jobs.FactReviewer", return_value=_PassReviewer()):
                    with patch("orchestrator.jobs.StyleReviewer", return_value=_PassReviewer()):
                        with patch("orchestrator.jobs.ComplianceReviewer", return_value=_FailingComplianceReviewer()):
                            await _async_run_generator_task(
                                dummy_task, str(gen.id), str(ke.id), "linkedin_post", "claude-opus-4-5", 0.0
                            )

        res = await db_session.execute(select(Artifact).where(Artifact.generation_id == gen.id))
        artifact = res.scalar_one()

        assert call_count == 1, "Compliance failure must NOT trigger auto-regeneration"
        assert artifact.review_status == ArtifactReviewStatus.FAILED
        assert artifact.retry_count == 0


# ─── 3. Compliance Override Endpoint ─────────────────────────────────────────

class TestComplianceOverrideEndpoint:
    """§3.10 / §7 — POST /api/v1/generations/{id}/artifacts/{type}/override"""

    async def test_override_preserves_failed_checks_and_generation_status(self, client, db_session: AsyncSession):
        """Valid reason records an attributed exception without certifying failed checks."""
        source = Source(
            extracted_text="Text",
            sensitivity=SensitivityLevel.INTERNAL,
            sensitivity_source=SensitivitySource.OPERATOR,
            sensitivity_confidence=1.0,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.PARTIAL_FAILURE,
        )
        db_session.add(gen)
        await db_session.flush()

        artifact = Artifact(
            generation_id=gen.id,
            output_type="linkedin_post",
            content="Sensitive post",
            review_status=ArtifactReviewStatus.FAILED,
            review_results=[{"reviewer_name": "compliance_reviewer", "passed": False}],
        )
        db_session.add(artifact)
        await db_session.commit()

        # Call override endpoint
        resp = await client.post(
            f"/api/v1/generations/{gen.id}/artifacts/linkedin_post/override",
            json={"reason": "Approved by CISO for executive disclosure."},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["review_status"] == "failed"
        assert body["decision"] == "overridden"
        assert body["reason"] == "Approved by CISO for executive disclosure."

        # Verify DB persisted ComplianceOverride row
        override_res = await db_session.execute(
            select(ComplianceOverride).where(ComplianceOverride.artifact_id == artifact.id)
        )
        override_row = override_res.scalar_one_or_none()
        assert override_row is not None
        assert override_row.reason == "Approved by CISO for executive disclosure."

        # Verify Artifact review_status was updated
        await db_session.refresh(artifact)
        assert artifact.review_status == ArtifactReviewStatus.FAILED

        # A compliance exception does not certify the generation
        await db_session.refresh(gen)
        assert gen.status == GenerationStatus.PARTIAL_FAILURE

    async def test_override_without_reason_returns_422(self, client, db_session: AsyncSession):
        """Override request with empty or missing reason must be rejected with 422."""
        source = Source(
            extracted_text="Text",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.PARTIAL_FAILURE,
        )
        db_session.add(gen)
        await db_session.flush()

        artifact = Artifact(
            generation_id=gen.id,
            output_type="linkedin_post",
            content="Post",
            review_status=ArtifactReviewStatus.FAILED,
        )
        db_session.add(artifact)
        await db_session.commit()

        # Empty reason string
        resp1 = await client.post(
            f"/api/v1/generations/{gen.id}/artifacts/linkedin_post/override",
            json={"reason": ""},
        )
        assert resp1.status_code == 422

        # Missing reason field
        resp2 = await client.post(
            f"/api/v1/generations/{gen.id}/artifacts/linkedin_post/override",
            json={},
        )
        assert resp2.status_code == 422
