"""
# Phase 4 Test Suite — Cost Tracking, Hard Budget Caps, Explainability, Feedback, Rerun, and Metrics.
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from agents.base import GeneratorArtifactResult
from cost.tracker import (
    build_artifact_cost_breakdown,
    compute_analyst_cost_share,
    load_pricing_config,
    tokens_to_cost,
)
from db.models import Artifact, ComplianceOverride, Generation, KnowledgeExtractionModel, Source
from db.session import get_db
from schemas.enums import (
    ArtifactReviewStatus,
    GenerationStatus,
    SensitivityLevel,
    SensitivitySource,
)

AUTH_HEADER = {"X-API-Key": "test-key"}


@pytest.fixture
def override_db(db_session: AsyncSession, monkeypatch):
    async def available_provider(configuration=None):
        return {"available": True, "model": "test-model", "message": "Ready"}
    monkeypatch.setattr("agents.availability.provider_health", available_provider)
    async def _get_db():
        yield db_session
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


# ─────────────────────────────────────────────────────────────────
# 1. Cost Tracker & Formula Tests
# ─────────────────────────────────────────────────────────────────

class TestCostTracker:
    def test_load_pricing_config(self):
        pricing = load_pricing_config()
        assert "claude-opus-4-5" in pricing
        assert pricing["claude-opus-4-5"]["input"] == 15.00
        assert pricing["claude-opus-4-5"]["output"] == 75.00

    def test_tokens_to_cost(self):
        usage = {"input_tokens": 100_000, "output_tokens": 10_000}
        cost = tokens_to_cost(usage, "claude-opus-4-5")
        assert cost == 2.25

    def test_compute_analyst_cost_share(self):
        usage = {"input_tokens": 100_000, "output_tokens": 10_000}
        share = compute_analyst_cost_share(usage, 3, "claude-opus-4-5")
        assert share == 0.75

    def test_build_artifact_cost_breakdown(self):
        history = [{"attempt_number": 1, "stage": "generation", "cost": 0.5}]
        breakdown = build_artifact_cost_breakdown(
            analyst_share=0.75,
            generation_usage={"input_tokens": 10_000, "output_tokens": 2_000},
            regeneration_usage={"input_tokens": 5_000, "output_tokens": 1_000},
            style_usage={"input_tokens": 1_000, "output_tokens": 500},
            fact_usage={"input_tokens": 1_000, "output_tokens": 500},
            compliance_usage={"input_tokens": 1_000, "output_tokens": 500},
            model="claude-opus-4-5",
            execution_history=history,
        )
        assert breakdown["analyst_share"] == 0.75
        assert breakdown["generation"] > 0
        assert breakdown["regeneration"] > 0
        assert breakdown["style_review"] > 0
        assert breakdown["fact_review"] > 0
        assert breakdown["compliance_review"] > 0
        assert breakdown["total"] == round(
            breakdown["analyst_share"]
            + breakdown["generation"]
            + breakdown["regeneration"]
            + breakdown["style_review"]
            + breakdown["fact_review"]
            + breakdown["compliance_review"],
            6,
        )
        assert breakdown["execution_history"] == history


# ─────────────────────────────────────────────────────────────────
# 2. Hard Budget Cap & Stage Boundary Gating
# ─────────────────────────────────────────────────────────────────

class TestBudgetCapsAndStageBoundaryPolicy:
    @pytest.mark.asyncio
    async def test_budget_exceeded_before_generator_skips_and_marks_status(
        self, db_session: AsyncSession, session_factory
    ):
        from orchestrator.jobs import _async_run_generator_task

        source = Source(
            extracted_text="Content",
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
            budget_type="tokens",
            budget_ceiling=100.0,
            budget_used=150.0,
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="S",
            entities={},
            facts=[],
            relationships=[],
            domain="tech",
            source_tone="neutral",
        )
        db_session.add(ke)
        await db_session.commit()

        mock_task = MagicMock()
        mock_task.request.retries = 0

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            await _async_run_generator_task(
                mock_task,
                str(gen.id),
                str(ke.id),
                "linkedin_post",
                "claude-opus-4-5",
                0.0,
            )

        res = await db_session.execute(
            select(Artifact).where(Artifact.generation_id == gen.id)
        )
        artifact = res.scalar_one()
        assert artifact.review_status == ArtifactReviewStatus.BUDGET_EXCEEDED
        assert artifact.content is None

    @pytest.mark.asyncio
    async def test_budget_exceeded_before_regeneration_delivers_without_regen(
        self, db_session: AsyncSession, session_factory
    ):
        from schemas.review import ReviewResult
        from orchestrator.jobs import _async_run_generator_task

        source = Source(
            extracted_text="Source content",
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
            budget_type="tokens",
            budget_ceiling=500.0,
            budget_used=0.0,
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="S",
            entities={},
            facts=[{"claim": "Fact 1", "source_span": "Source span", "start_char": 0, "end_char": 10, "confidence": 1.0}],
            relationships=[],
            domain="tech",
            source_tone="neutral",
        )
        db_session.add(ke)
        await db_session.commit()

        mock_gen_result = GeneratorArtifactResult(
            output_type="linkedin_post",
            content="Generated draft with failing fact",
            facts_used=[{"claim": "Fact 1"}],
            prompt_version="1.0.0",
            model_version="claude-opus-4-5",
            token_usage={"input_tokens": 400, "output_tokens": 200},
        )

        mock_style_res = ReviewResult(reviewer_name="style", passed=True, details={"token_usage": {"input_tokens": 10, "output_tokens": 10}}, reviewer_version="1.0.0")
        mock_fact_res = ReviewResult(reviewer_name="fact", passed=False, details={"failing_claims": ["Unverified claim"], "token_usage": {"input_tokens": 10, "output_tokens": 10}}, reviewer_version="1.0.0")
        mock_comp_res = ReviewResult(reviewer_name="compliance", passed=True, details={"token_usage": {"input_tokens": 10, "output_tokens": 10}}, reviewer_version="1.0.0")


        mock_task = MagicMock()
        mock_task.request.retries = 0

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory), \
             patch("orchestrator.jobs.GenericGeneratorAgent.generate", new_callable=AsyncMock) as mock_gen, \
             patch("orchestrator.jobs.StyleReviewer.review", new_callable=AsyncMock) as mock_s, \
             patch("orchestrator.jobs.FactReviewer.review", new_callable=AsyncMock) as mock_f, \
             patch("orchestrator.jobs.ComplianceReviewer.review", new_callable=AsyncMock) as mock_c:

            mock_gen.return_value = mock_gen_result
            mock_s.return_value = mock_style_res
            mock_f.return_value = mock_fact_res
            mock_c.return_value = mock_comp_res

            await _async_run_generator_task(
                mock_task,
                str(gen.id),
                str(ke.id),
                "linkedin_post",
                "claude-opus-4-5",
                0.0,
            )

        res = await db_session.execute(
            select(Artifact).where(Artifact.generation_id == gen.id)
        )
        artifact = res.scalar_one()
        assert artifact.review_status == ArtifactReviewStatus.BUDGET_EXCEEDED
        assert artifact.retry_count == 0
        assert len(artifact.cost["execution_history"]) == 2
        assert artifact.cost["execution_history"][1]["outcome"] == "budget_exceeded_before_regeneration"


# ─────────────────────────────────────────────────────────────────
# 3. Explainability, Citations & Provenance
# ─────────────────────────────────────────────────────────────────

class TestExplainabilityAndFactProvenance:
    @pytest.mark.asyncio
    async def test_get_artifact_full_explainability_payload(
        self, db_session: AsyncSession, override_db
    ):
        source = Source(
            extracted_text="Original text.",
            sensitivity=SensitivityLevel.CONFIDENTIAL,
            sensitivity_source=SensitivitySource.OPERATOR,
            sensitivity_confidence=1.0,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            prompt_version="linkedin_post@1.0.0",
            model_version="claude-opus-4-5",
            reviewer_version="style@1.0.0; fact@1.0.0; compliance@1.0.0",
            status=GenerationStatus.COMPLETED,
        )
        db_session.add(gen)
        await db_session.flush()

        artifact = Artifact(
            generation_id=gen.id,
            output_type="linkedin_post",
            content="Ground truth post",
            review_status=ArtifactReviewStatus.PASSED,
            review_results=[{"reviewer_name": "fact", "passed": True}],
            facts_used=[{
                "fact_source_id": "fact_12345678_0",
                "claim": "Claim 1",
                "source_span": "Original text.",
                "start_char": 0,
                "end_char": 14,
                "confidence": 1.0,
            }],
            cost={
                "analyst_share": 0.5,
                "generation": 0.2,
                "total": 0.7,
                "execution_history": [{"attempt_number": 1, "stage": "generation", "cost": 0.2}],
            },
        )
        db_session.add(artifact)
        await db_session.flush()

        override = ComplianceOverride(
            artifact_id=artifact.id,
            operator_id="operator_audit_test",
            reason="Approved for secure audience",
        )
        db_session.add(override)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/generations/{gen.id}/artifacts/linkedin_post",
                headers=AUTH_HEADER,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["output_type"] == "linkedin_post"
        assert data["sensitivity"] == "confidential"
        assert data["sensitivity_source"] == "operator"
        assert data["sensitivity_confidence"] == 1.0
        assert data["facts_used"][0]["fact_source_id"] == "fact_12345678_0"
        assert data["cost"]["execution_history"][0]["stage"] == "generation"
        assert data["compliance_override"]["operator_id"] == "operator_audit_test"
        assert data["compliance_override"]["reason"] == "Approved for secure audience"


# ─────────────────────────────────────────────────────────────────
# 4. Human Feedback Endpoint & Metadata
# ─────────────────────────────────────────────────────────────────

class TestHumanFeedbackMetadata:
    @pytest.mark.asyncio
    async def test_submit_feedback_persists_full_version_metadata(
        self, db_session: AsyncSession, override_db
    ):
        source = Source(
            extracted_text="Content",
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
            prompt_version="linkedin_post@1.0.0",
            model_version="claude-opus-4-5",
            status=GenerationStatus.COMPLETED,
        )
        db_session.add(gen)
        await db_session.flush()

        artifact = Artifact(
            generation_id=gen.id,
            output_type="linkedin_post",
            content="Content to rate",
            review_status=ArtifactReviewStatus.PASSED,
        )
        db_session.add(artifact)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/generations/{gen.id}/artifacts/linkedin_post/feedback",
                json={"rating": "positive", "comment": "Excellent adherence to tone."},
                headers=AUTH_HEADER,
            )

        assert resp.status_code == 200
        data = resp.json()
        fb = data["feedback"]
        assert fb["rating"] == "positive"
        assert fb["comment"] == "Excellent adherence to tone."
        from evidence.validation import version
        assert fb["artifact_version"] == f"{artifact.id}@{version(artifact.content)}"
        assert fb["prompt_version"] == "linkedin_post@1.0.0"
        assert fb["model_version"] == "claude-opus-4-5"
        assert fb["operator_id"] == "operator-62af8704764f"
        assert "submitted_at" in fb


# ─────────────────────────────────────────────────────────────────
# 5. Fresh-Budget Rerun
# ─────────────────────────────────────────────────────────────────

class TestFreshBudgetRerun:
    @pytest.mark.asyncio
    async def test_rerun_endpoint_enqueues_task(
        self, db_session: AsyncSession, override_db
    ):
        source = Source(
            extracted_text="Content",
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
            content=None,
            review_status=ArtifactReviewStatus.BUDGET_EXCEEDED,
        )
        db_session.add(artifact)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("api.routes.generations.run_rerun_artifact_task.delay") as mock_delay:
                mock_delay.return_value = MagicMock(id="rerun_task_1")
                resp = await client.post(
                    f"/api/v1/generations/{gen.id}/artifacts/linkedin_post/rerun",
                    json={"budget_type": "cost_usd", "budget_ceiling": 5.0},
                    headers=AUTH_HEADER,
                )

        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"
        mock_delay.assert_not_called()
        from db.models import DurableJob
        from uuid import UUID
        fresh_id = UUID(resp.json()["generation_id"])
        assert fresh_id != gen.id
        queued = await db_session.get(DurableJob, fresh_id)
        assert queued.status == "queued"
        fresh = await db_session.get(Generation, fresh_id)
        assert fresh.budget_type == "cost_usd" and fresh.budget_ceiling == 5.0



# ─────────────────────────────────────────────────────────────────
# 6. System Metrics Endpoint
# ─────────────────────────────────────────────────────────────────

class TestSystemMetricsEndpoint:
    @pytest.mark.asyncio
    async def test_metrics_endpoint_aggregations(
        self, db_session: AsyncSession, override_db
    ):
        source = Source(
            extracted_text="Content",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen1 = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.COMPLETED,
            total_tokens=1000,
            total_cost_usd=0.05,
            rerun_count=1,
        )
        gen2 = Generation(
            source_id=source.id,
            output_types=["twitter_post"],
            params={},
            status=GenerationStatus.PARTIAL_FAILURE,
            total_tokens=2000,
            total_cost_usd=0.10,
            rerun_count=0,
        )
        db_session.add_all([gen1, gen2])
        await db_session.flush()

        art1 = Artifact(
            generation_id=gen1.id,
            output_type="linkedin_post",
            review_status=ArtifactReviewStatus.PASSED,
        )
        art2 = Artifact(
            generation_id=gen2.id,
            output_type="twitter_post",
            review_status=ArtifactReviewStatus.FAILED,
        )
        art3 = Artifact(
            generation_id=gen2.id,
            output_type="slack_update",
            review_status=ArtifactReviewStatus.BUDGET_EXCEEDED,
        )
        db_session.add_all([art1, art2, art3])
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/metrics",
                headers=AUTH_HEADER,
            )

        assert resp.status_code == 200
        m = resp.json()
        assert m["total_generations"] == 2
        assert m["total_artifacts"] == 3
        assert m["artifact_success_rate"] == round(1 / 3, 4)
        assert m["reviewer_rejection_rate"] == round(1 / 3, 4)
        assert m["budget_exceeded_count"] == 1
        assert m["rerun_count"] == 1
        assert m["total_tokens_used"] == 3000
        assert m["total_cost_usd"] == 0.15
        assert m["average_cost_per_generation"] == round(0.15 / 2, 6)
        assert m["average_cost_per_artifact"] == round(0.15 / 3, 6)


# ─────────────────────────────────────────────────────────────────
# 7. Atomic Concurrency Safety Test
# ─────────────────────────────────────────────────────────────────

class TestConcurrentBudgetAccounting:
    @pytest.mark.asyncio
    async def test_parallel_atomic_record_usage(
        self, db_session: AsyncSession, session_factory
    ):
        from orchestrator.jobs import _atomic_record_usage

        source = Source(
            extracted_text="Content",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["a", "b", "c"],
            params={},
            budget_type="tokens",
            budget_ceiling=10000.0,
            budget_used=0.0,
            total_tokens=0,
            total_cost_usd=0.0,
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.commit()

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            tasks = [
                _atomic_record_usage(str(gen.id), tokens=100, cost=0.01)
                for _ in range(10)
            ]
            await asyncio.gather(*tasks)

        await db_session.refresh(gen)
        assert gen.total_tokens == 1000
        assert gen.total_cost_usd == 0.10
        assert gen.budget_used == 1000.0
