"""
# §3.8 / §6 Unit & Integration Tests for Evaluation Framework & Regression Guard.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from eval.dataset_loader import load_dataset_samples
from eval.provenance_validator import validate_provenance_integrity
from eval.regression_guard import RegressionGuard


class TestDatasetLoader:
    def test_load_v1_golden_dataset(self):
        samples = load_dataset_samples(version="v1")
        assert len(samples) >= 5
        domains = {s.domain.value for s in samples}
        assert "incident_report" in domains
        assert "policy_document" in domains
        assert "news_article" in domains
        assert "adversarial" in domains

    def test_sample_has_required_attributes(self):
        samples = load_dataset_samples(version="v1")
        sample = samples[0]
        assert sample.id is not None
        assert len(sample.source_document) > 20
        assert isinstance(sample.ground_truth_claims, list)


class TestProvenanceValidator:
    def test_verified_claims_pass(self):
        source = "Apple reported Q3 2024 revenue of $85.8 billion with net income of $21.4B."
        facts_used = [
            {
                "claim": "Apple reported Q3 2024 revenue of $85.8 billion.",
                "source_span": "revenue of $85.8 billion",
                "start_char": 23,
                "end_char": 47,
            }
        ]
        report = validate_provenance_integrity(
            artifact_content="Apple had $85.8B revenue in Q3.",
            facts_used=facts_used,
            source_text=source,
        )
        assert report.is_valid is True
        assert report.verified_claims == 1
        assert report.unsupported_claims == 0
        assert report.hallucination_rate == 0.0

    def test_unanchored_claim_flagged_as_unverified(self):
        source = "Company revenue was $10M."
        facts_used = [
            {
                "claim": "Profit grew by 800% under secret deal.",
                "source_span": "secret deal revenue of $500M",
            }
        ]
        report = validate_provenance_integrity(
            artifact_content="Profit grew 800%.",
            facts_used=facts_used,
            source_text=source,
        )
        assert report.is_valid is False
        assert report.unsupported_claims == 1
        assert report.hallucination_rate == 1.0


class TestRegressionGuard:
    def test_stable_metrics_pass(self):
        current = {
            "fact_accuracy": 0.96,
            "hallucination_rate": 0.01,
            "citation_coverage": 0.98,
            "avg_latency": 3200.0,
            "avg_cost": 0.005,
        }
        baseline = {
            "fact_accuracy": 0.95,
            "hallucination_rate": 0.01,
            "citation_coverage": 0.97,
            "avg_latency": 3300.0,
            "avg_cost": 0.005,
        }
        report = RegressionGuard.evaluate(current, baseline)
        assert report.has_regressed is False

    def test_accuracy_drop_fails_guard(self):
        current = {
            "fact_accuracy": 0.88,  # > 3% drop
            "hallucination_rate": 0.01,
            "citation_coverage": 0.98,
        }
        baseline = {
            "fact_accuracy": 0.95,
            "hallucination_rate": 0.01,
            "citation_coverage": 0.98,
        }
        report = RegressionGuard.evaluate(current, baseline)
        assert report.has_regressed is True

    def test_citation_coverage_below_floor_fails_guard(self):
        current = {
            "fact_accuracy": 0.96,
            "hallucination_rate": 0.01,
            "citation_coverage": 0.91,  # < 95% floor
        }
        report = RegressionGuard.evaluate(current)
        assert report.has_regressed is True


class TestEvaluationAPI:
    @pytest.mark.asyncio
    async def test_get_latest_evaluation_includes_dataset_size(self, client: AsyncClient, db_session):
        """PRD Principle: Never publish numbers without sample size (§3.8, §10)."""
        from db.models import EvaluationRun
        db_session.add(EvaluationRun(dataset_version="fixture-v1", dataset_size=3, fact_accuracy=0.5))
        await db_session.commit()
        response = await client.get("/api/v1/evaluations/latest")
        assert response.status_code == 200
        data = response.json()
        assert "dataset_size" in data
        assert data["dataset_size"] > 0
        assert "fact_accuracy" in data
        assert "dataset_size_caption" in data
        assert str(data["dataset_size"]) in data["dataset_size_caption"]
