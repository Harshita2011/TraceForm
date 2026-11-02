"""
# Enterprise Content Generation Layer Test Suite (Phases 1–10)
# Validates Audience-Aware Blueprints, InsightEngine, RecommendationEngine,
# Narrative Frameworks, Differentiation Engine (<0.75), Anti-AI Reviewer,
# 7-Dimension Executive Communication Scoring, and Golden Benchmark Suite.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.generators.base import GenericGeneratorAgent
from agents.generators.blueprints import BLUEPRINT_REGISTRY, get_blueprint
from agents.generators.differentiation import (
    ArtifactDifferentiationEngine,
    compute_pairwise_similarity,
    validate_artifact_differentiation,
)
from agents.generators.insight_engine import InsightEngine, SynthesizedInsights
from agents.generators.recommendation_engine import RecommendationEngine, SynthesizedRecommendations
from agents.generators.section_validator import heal_artifact_sections, validate_artifact_sections
from agents.reviewers.style_quality import StyleQualityReviewer, audit_anti_ai_writing
from cost.quality_scoring import calculate_artifact_quality_score
from schemas.generation import GenerationParams
from tests.fixtures.knowledge_extraction import APPLE_REVENUE_EXTRACTION, MINIMAL_EXTRACTION


# ─────────────────────────────────────────────────────────────
# Phase 1: Audience-Aware Blueprints Tests
# ─────────────────────────────────────────────────────────────

class TestAudienceAwareBlueprints:
    def test_all_blueprints_have_audience_and_communication_goals(self):
        """Verify all 11 registered blueprints have explicit audience, goal, action, depth, and tone."""
        expected_types = [
            "executive_briefing", "linkedin_post", "press_release", "strategic_memo",
            "research_report", "policy_memo", "presentation", "infographic",
            "newsletter", "twitter_x", "video_package"
        ]
        for key in expected_types:
            bp = get_blueprint(key)
            assert bp.target_audience != "", f"{key} missing target_audience"
            assert bp.communication_goal != "", f"{key} missing communication_goal"
            assert bp.desired_action != "", f"{key} missing desired_action"
            assert bp.reading_depth in ["Strategic", "Executive-BLUF", "Deep-Dive", "Scan-Optimized", "Conversational", "Factual"], f"{key} invalid reading_depth {bp.reading_depth}"
            assert bp.tone_profile != "", f"{key} missing tone_profile"
            assert len(bp.narrative_framework) >= 3, f"{key} narrative framework too short"
            assert len(bp.anti_ai_rules) > 0, f"{key} missing anti_ai_rules"


# ─────────────────────────────────────────────────────────────
# Phase 2 & 7: InsightEngine & Thought Leadership Tests
# ─────────────────────────────────────────────────────────────

class TestInsightEngine:
    def test_insight_extraction_from_knowledge(self):
        engine = InsightEngine()
        insights = engine.extract_insights(APPLE_REVENUE_EXTRACTION)

        assert isinstance(insights, SynthesizedInsights)
        assert len(insights.executive_thesis) > 20
        assert len(insights.key_findings) > 0
        # Deterministic guidance must not invent strategic implications.
        assert insights.strategic_opportunities == []
        assert insights.contrarian_insights == []
        assert all(item.raw_fact in [fact.claim for fact in APPLE_REVENUE_EXTRACTION.facts]
                   for item in insights.all_insights())

        # Check prompt rendering
        guidance = insights.to_guidance_prompt()
        assert "STRATEGIC EXECUTIVE THESIS" in guidance
        assert "KEY STRATEGIC FINDINGS" in guidance

    def test_insight_extraction_anomalies_and_implications(self):
        engine = InsightEngine()
        insights = engine.extract_insights(APPLE_REVENUE_EXTRACTION)
        all_ins = insights.all_insights()

        for ins in all_ins:
            assert ins.headline != ""
            assert ins.strategic_implication != ""
            assert ins.second_order_impact != ""


# ─────────────────────────────────────────────────────────────
# Phase 4: RecommendationEngine Tests
# ─────────────────────────────────────────────────────────────

class TestRecommendationEngine:
    def test_recommendation_generation(self):
        engine = RecommendationEngine()
        recs = engine.generate_recommendations(APPLE_REVENUE_EXTRACTION)

        assert isinstance(recs, SynthesizedRecommendations)
        assert len(recs.decision_statement) > 10
        # Source facts do not establish owners, deadlines or ROI; do not fabricate them.
        assert recs.all_recommendations() == []
        assert "unless present in the source" in recs.decision_statement

        # Check prompt guidance
        prompt_guidance = recs.to_guidance_prompt()
        assert "STRATEGIC RECOMMENDATIONS" in prompt_guidance
        assert "DECISION REQUIRED" in prompt_guidance


# ─────────────────────────────────────────────────────────────
# Phase 5: Differentiation Engine (<0.75 Cosine Similarity) Tests
# ─────────────────────────────────────────────────────────────

class TestDifferentiationEngine:
    def test_cross_artifact_similarity_guardrail(self):
        """Validate that distinctly written artifacts have similarity strictly below 0.75."""
        exec_text = (
            "## Executive Summary\nApple achieved Q3 revenue of $85.8B with 34% YoY growth.\n\n"
            "## Business Impact\nCAC expanded to 22 months due to enterprise customer churn.\n\n"
            "## Decision Required\nApprove $1.2M budget reallocation."
        )
        linkedin_text = (
            "## Hook\nWhy do 84% of founders misdiagnose customer churn?\n\n"
            "## Story\nLast quarter, customer onboarding latency blew past 48 days.\n\n"
            "## Call To Action\nWhat is your average time to first value? Drop comments below."
        )
        pr_text = (
            "## Headline\nAPPLE REPORTS RECORD Q3 REVENUE OF $85.8 BILLION\n\n"
            "## Announcement\nCUPERTINO, CA — August 31, 2026 — Apple today announced record Q3 revenue.\n\n"
            "## Quote\n'We continue to invest in breakthrough customer experiences,' said CEO Tim Cook."
        )

        artifacts = {
            "executive_briefing": exec_text,
            "linkedin_post": linkedin_text,
            "press_release": pr_text,
        }

        engine = ArtifactDifferentiationEngine(threshold=0.75)
        report = engine.evaluate(artifacts)

        assert report.is_differentiated, f"Artifacts flagged as too similar: {report.flagged_pairs}"
        assert report.max_similarity < 0.75, f"Max similarity {report.max_similarity} exceeded 0.75"
        for t, score in report.uniqueness_scores.items():
            assert score.uniqueness_score >= 60.0
            assert not score.is_generic


# ─────────────────────────────────────────────────────────────
# Phase 6: Anti-AI Writing Reviewer Tests
# ─────────────────────────────────────────────────────────────

class TestAntiAIReviewer:
    def test_detects_cliches_and_generic_openings(self):
        bad_ai_text = (
            "In today's rapidly evolving landscape, it is important to note that customer retention is crucial. "
            "Furthermore, we must delve into the tapestry of customer feedback. "
            "In conclusion, this highlights the importance of innovation."
        )
        audit = audit_anti_ai_writing(bad_ai_text, output_type="executive_briefing")

        assert not audit.passed
        assert audit.quality_score < 75.0
        assert audit.generic_opening_flagged
        assert len(audit.detected_cliches) >= 2
        assert len(audit.editorial_suggestions) > 0

    def test_passes_clean_executive_content(self):
        clean_text = (
            "## Executive Summary\n"
            "Customer acquisition grew 34% YoY to $8.4M ARR, but net retention contracted 500 bps as churn reached 9%. "
            "Prolonged onboarding latency averaging 48 days against a 21-day SLA is the primary operational driver.\n\n"
            "## Business Impact\n"
            "Payback cycles lengthened from 14 to 22 months.\n\n"
            "## Decision Required\n"
            "Authorize $1.2M Q4 budget reallocation to customer engineering."
        )
        audit = audit_anti_ai_writing(clean_text, output_type="executive_briefing")

        assert audit.passed
        assert audit.quality_score >= 85.0
        assert not audit.generic_opening_flagged
        assert len(audit.detected_cliches) == 0

    async def test_style_quality_reviewer_agent(self, monkeypatch):
        monkeypatch.setattr("agents.reviewers.style_quality.call_llm", AsyncMock(return_value=(
            json.dumps({"passed": True, "quality_score": 90, "reasoning": "Fixture review", "issues": []}),
            {"input_tokens": 10, "output_tokens": 10},
        )))
        reviewer = StyleQualityReviewer(client=object())
        clean_text = (
            "## Executive Summary\n"
            "Revenue reached $85.8B, driven by services expansion and disciplined capital allocation.\n\n"
            "## Decision Required\n"
            "Approve FY27 investment priority."
        )
        params = GenerationParams(output_type="executive_briefing")
        result = await reviewer.review(clean_text, APPLE_REVENUE_EXTRACTION, params)

        assert result.reviewer_name == "style_quality_reviewer"
        assert result.passed
        assert "combined_score" in result.details


# ─────────────────────────────────────────────────────────────
# Phase 8: 7-Dimension Executive Communication Scoring Tests
# ─────────────────────────────────────────────────────────────

class TestExecutiveCommunicationScoring:
    def test_seven_dimension_quality_scoring(self):
        content = (
            "## Executive Summary\n"
            "Gross ARR reached $8.4M (112% of target) while net retention dipped to 91% as churn reached 9%. "
            "Onboarding delays averaging 48 days drive $3.8M in revenue erosion.\n\n"
            "## Business Impact\n"
            "CAC payback expanded to 22 months.\n\n"
            "## Recommendations\n"
            "1. P0 (0–30 Days): Reallocate $1.2M to customer engineering.\n"
            "2. P1 (30–60 Days): Enforce 21-day SLA.\n\n"
            "## Decision Required\n"
            "Authorize $1.2M budget reallocation."
        )
        breakdown = calculate_artifact_quality_score(
            content=content,
            section_compliance_score=1.0,
            citations_count=3,
            reviewer_outcomes=[{"passed": True, "score": 0.95}],
            differentiation_score=94.0,
            output_type="executive_briefing",
        )

        assert breakdown.composite_score >= 80.0
        assert breakdown.insight_density >= 70.0
        assert breakdown.strategic_value >= 70.0
        assert breakdown.actionability >= 70.0
        assert breakdown.narrative_flow >= 70.0
        assert breakdown.audience_fit >= 70.0
        assert breakdown.differentiation >= 70.0
        assert breakdown.readability >= 70.0


# ─────────────────────────────────────────────────────────────
# Phase 9: Golden Artifact Benchmark Suite Tests
# ─────────────────────────────────────────────────────────────

class TestGoldenArtifactBenchmarkSuite:
    def test_all_golden_benchmark_files_exist_and_valid(self):
        """Verify all 11 golden benchmark files exist in docs/examples/golden-artifacts/ and have required sections."""
        golden_dir = Path(__file__).resolve().parents[2] / "docs" / "examples" / "golden-artifacts"
        assert golden_dir.exists() and golden_dir.is_dir()

        for key, bp in BLUEPRINT_REGISTRY.items():
            golden_path = golden_dir / f"{key}.md"
            assert golden_path.exists(), f"Missing golden file for {key} at {golden_path}"

            content = golden_path.read_text(encoding="utf-8")
            assert len(content) > 100, f"Golden file for {key} is too short"

            # Check section validation against blueprint
            sec_val = validate_artifact_sections(content, bp)
            assert sec_val.compliance_score >= 0.80, (
                f"Golden file for {key} failed section compliance: missing {sec_val.missing_sections}"
            )

            # Check anti-AI audit on golden file
            audit = audit_anti_ai_writing(content, output_type=key)
            assert audit.passed, f"Golden file for {key} failed anti-AI audit: {audit.detected_cliches}"


# ─────────────────────────────────────────────────────────────
# Phase 10: Generator Self-Healing & Refinement Tests
# ─────────────────────────────────────────────────────────────

class TestGeneratorSelfHealing:
    def test_section_self_healing_synthesis(self):
        """If an LLM produces content missing a section, self-healing synthesizes it."""
        incomplete_exec = (
            "## Executive Summary\n"
            "Revenue reached $85.8B with 34% growth.\n\n"
            "## Business Impact\n"
            "Unit economics remain sound."
        )
        bp = get_blueprint("executive_briefing")
        val_before = validate_artifact_sections(incomplete_exec, bp)
        assert not val_before.is_valid
        assert "Decision Required" in val_before.missing_sections

        healed = heal_artifact_sections(incomplete_exec, bp, APPLE_REVENUE_EXTRACTION)
        val_after = validate_artifact_sections(healed, bp)

        assert val_after.is_valid
        assert "Decision Required" in healed
        assert "Recommendations" in healed
