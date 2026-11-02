"""
Unit tests for Artifact Differentiation Enforcement & Blueprint Registry (§3.3).
Validates:
1. Blueprint Registry completeness (Role, Audience, Objective, Tone, Writing Style, Sections, Forbidden Patterns, Success Criteria).
2. Multi-dimensional similarity scoring (TF-IDF cosine, Jaccard lexical, structural overlap).
3. MAX_ALLOWED_SIMILARITY = 0.55 threshold enforcement.
4. Artifact uniqueness scoring (>85 target, <80 generic detection).
"""

import pytest
from agents.generators.blueprints import BLUEPRINT_REGISTRY, get_blueprint
from agents.generators.differentiation import (
    MAX_ALLOWED_SIMILARITY,
    compute_pairwise_similarity,
    calculate_artifact_uniqueness,
    validate_artifact_differentiation,
)


def test_blueprint_registry_schema_completeness():
    """Every registered blueprint must define all required attributes."""
    expected_blueprints = [
        "executive_briefing",
        "linkedin_post",
        "press_release",
        "strategic_memo",
        "research_report",
        "policy_memo",
        "presentation",
        "infographic",
        "newsletter",
        "twitter_x",
        "video_package",
    ]
    for bp_id in expected_blueprints:
        bp = get_blueprint(bp_id)
        assert bp is not None, f"Missing blueprint for {bp_id}"
        assert bp.role, f"Missing role in {bp_id}"
        assert bp.audience, f"Missing audience in {bp_id}"
        assert bp.objective, f"Missing objective in {bp_id}"
        assert bp.tone, f"Missing tone in {bp_id}"
        assert bp.writing_style, f"Missing writing_style in {bp_id}"
        assert len(bp.sections) >= 4, f"Insufficient sections in {bp_id}"
        assert len(bp.anti_patterns) >= 2, f"Missing anti_patterns in {bp_id}"
        assert len(bp.success_criteria) >= 1, f"Missing success_criteria in {bp_id}"


def test_similarity_threshold_enforcement():
    """Identical content must exceed 0.55 threshold; differentiated content must be below."""
    text_exec = """## Executive Summary
Bottom line: Core operations demonstrate verifiable compliance.
## Business Impact
• Revenue and margin stability verified.
## Opportunities
• Deploy capital into high-growth units.
## Risks
• Downside execution latency.
## Recommendations
1. Authorize immediate milestone deployment.
## Decision Required
CEO approval requested."""

    text_press = """## Headline
ORGANIZATION ANNOUNCES MAJOR OPERATIONAL MILESTONE
## Subheadline
Verified achievements establish new performance benchmark.
## Announcement
SAN FRANCISCO — Today leadership confirmed operational milestones.
## Quote
"This achievement underscores our commitment," said leadership.
## Closing Statement
TraceForm will continue rollout across enterprise units.
## Media Contact
Corporate Communications: press@traceform.internal"""

    # Compare identical texts
    identical_sim = compute_pairwise_similarity("exec_1", text_exec, "exec_2", text_exec)
    assert identical_sim.composite_similarity > MAX_ALLOWED_SIMILARITY
    assert identical_sim.exceeds_threshold is True

    # Compare differentiated texts
    diff_sim = compute_pairwise_similarity("executive_briefing", text_exec, "press_release", text_press)
    assert diff_sim.composite_similarity <= MAX_ALLOWED_SIMILARITY
    assert diff_sim.exceeds_threshold is False


def test_artifact_uniqueness_scoring():
    """Uniqueness score must exceed 85 for differentiated artifacts and drop below 80 for generic/duplicate artifacts."""
    text_exec = """## Executive Summary
Bottom line: Factual claims grounded in source.
## Business Impact
• Impact verified across units.
## Opportunities
• Growth potential confirmed.
## Risks
• Execution risks identified.
## Recommendations
1. Deploy resources.
## Decision Required
CEO sign-off."""

    text_linkedin = """## Hook
Most teams misunderstand execution.
## Story
Here is what the numbers prove.
## Insight
Verified systems win.
## Takeaway
1. Move fast with proof.
## Call To Action
What is your take?
## Hashtags
#Strategy #Leadership"""

    artifacts = {
        "executive_briefing": text_exec,
        "linkedin_post": text_linkedin,
    }

    report = validate_artifact_differentiation(artifacts)
    assert report.is_differentiated is True
    assert report.max_similarity <= MAX_ALLOWED_SIMILARITY

    exec_score = report.uniqueness_scores["executive_briefing"]
    assert exec_score.uniqueness_score >= 85.0
    assert exec_score.is_generic is False

    # Simulate duplicate/generic output
    duplicate_artifacts = {
        "executive_briefing": text_exec,
        "press_release": text_exec,  # Press release copied from Executive summary
    }
    dup_report = validate_artifact_differentiation(duplicate_artifacts)
    assert dup_report.is_differentiated is False
    assert dup_report.max_similarity > MAX_ALLOWED_SIMILARITY
    assert len(dup_report.flagged_pairs) >= 1
