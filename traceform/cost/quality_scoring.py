"""
# §3.5 Artifact Quality Scoring & Executive Communication Scoring (Phase 8)
# Scores across 7 Executive Communication dimensions (0–100):
#   1. Insight Density
#   2. Strategic Value
#   3. Actionability
#   4. Narrative Flow
#   5. Audience Fit
#   6. Differentiation
#   7. Readability & Polish
# Returns granular breakdown and weighted composite score.
"""

from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field


class QualityScoreBreakdown(BaseModel):
    # Legacy base dimensions
    format_compliance: float = Field(default=95.0, ge=0.0, le=100.0, description="Section presence & structure (0-100)")
    citation_coverage: float = Field(default=90.0, ge=0.0, le=100.0, description="Fact grounding & citation density (0-100)")
    review_pass_rate: float = Field(default=95.0, ge=0.0, le=100.0, description="Reviewer audit pass scores (0-100)")
    readability: float = Field(default=90.0, ge=0.0, le=100.0, description="Readability & scanability (0-100)")

    # Phase 8 — 7-Dimension Executive Communication Scoring
    insight_density: float = Field(default=90.0, ge=0.0, le=100.0, description="Ratio of high-value strategic interpretations to words (0-100)")
    strategic_value: float = Field(default=90.0, ge=0.0, le=100.0, description="Presence of actionable business implications & ROI (0-100)")
    actionability: float = Field(default=90.0, ge=0.0, le=100.0, description="Clarity of next steps, owners, and decision criteria (0-100)")
    narrative_flow: float = Field(default=92.0, ge=0.0, le=100.0, description="Progression across format's narrative framework (0-100)")
    audience_fit: float = Field(default=95.0, ge=0.0, le=100.0, description="Persona register and tone alignment (0-100)")
    differentiation: float = Field(default=94.0, ge=0.0, le=100.0, description="Uniqueness compared to other artifacts (0-100)")

    composite_score: float = Field(ge=0.0, le=100.0, description="Weighted composite score (0-100)")


def _compute_readability(content: str) -> float:
    """Estimates readability score from average sentence length and paragraph structure."""
    if not content:
        return 50.0
    sentences = re.split(r"[.!?]+", content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]

    if not sentences:
        return 70.0

    avg_words_per_sentence = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

    # Ideal executive readability is 12-22 words per sentence
    if 10 <= avg_words_per_sentence <= 22:
        score = 95.0
    elif 8 <= avg_words_per_sentence <= 28:
        score = 88.0
    else:
        score = 75.0

    # Boost if markdown formatting (bullet points, bolding) is used
    if "*" in content or "-" in content or "#" in content:
        score = min(100.0, score + 4.0)

    return round(score, 1)


def _compute_insight_density(content: str, citations_count: int) -> float:
    """Evaluates insight density based on quantitative metrics, implications, and citations."""
    if not content:
        return 0.0
    words = content.split()
    word_count = len(words)
    if word_count == 0:
        return 0.0

    # Look for quantitative tokens ($X, X%, numbers, bps)
    quant_tokens = len(re.findall(r"(?:\$\d+|\d+(?:\.\d+)?%|\b\d+\s*(?:bps|days|months|ARR|CAC)\b)", content, re.IGNORECASE))
    implication_markers = len(re.findall(r"\b(?:signal|impact|result|implication|consequence|because|yielding|driving|threat|lead to)\b", content, re.IGNORECASE))

    density_raw = ((quant_tokens * 4.0) + (implication_markers * 3.0) + (citations_count * 5.0)) / max(word_count / 50.0, 1.0)
    score = min(100.0, max(50.0, 60.0 + (density_raw * 6.0)))
    return round(score, 1)


def _compute_strategic_value(content: str) -> float:
    """Evaluates presence of ROI, risk-adjusted outcomes, and 2nd-order implications."""
    if not content:
        return 0.0
    value_terms = ["roi", "arr", "ebitda", "cac", "payback", "margin", "valuation", "risk", "mitigat", "downside", "opportunity", "revenue", "bottleneck", "sla"]
    count = sum(1 for term in value_terms if term in content.lower())
    score = min(100.0, max(60.0, 65.0 + (count * 3.0)))
    return round(score, 1)


def _compute_actionability(content: str) -> float:
    """Evaluates clarity of recommendations, timelines, and decision frameworks."""
    if not content:
        return 0.0
    action_terms = ["recommend", "decision", "p0", "p1", "p2", "timeline", "owner", "approve", "mandate", "execute", "steps", "call to action", "hashtag", "cta"]
    count = sum(1 for term in action_terms if term in content.lower())
    score = min(100.0, max(60.0, 68.0 + (count * 3.5)))
    return round(score, 1)


def calculate_artifact_quality_score(
    content: str | None,
    section_compliance_score: float,  # 0.0 to 1.0
    citations_count: int,
    reviewer_outcomes: list[dict] | None = None,
    differentiation_score: float = 94.0,
    output_type: str = "executive_briefing",
) -> QualityScoreBreakdown:
    """
    Computes transparent composite quality score for an artifact across 7 Executive Communication dimensions.
    """
    if not content:
        return QualityScoreBreakdown(
            format_compliance=0.0,
            citation_coverage=0.0,
            review_pass_rate=0.0,
            readability=0.0,
            insight_density=0.0,
            strategic_value=0.0,
            actionability=0.0,
            narrative_flow=0.0,
            audience_fit=0.0,
            differentiation=0.0,
            composite_score=0.0,
        )

    # 1. Format compliance (0-100)
    format_comp = round(section_compliance_score * 100.0, 1)

    # 2. Citation coverage (0-100)
    if citations_count >= 5:
        citation_cov = 98.0
    elif citations_count >= 3:
        citation_cov = 92.0
    elif citations_count >= 1:
        citation_cov = 82.0
    else:
        citation_cov = 60.0

    # 3. Review pass rate (0-100)
    if reviewer_outcomes and len(reviewer_outcomes) > 0:
        scores = []
        for r in reviewer_outcomes:
            if not isinstance(r, dict) or "_traceform_meta" in r:
                continue
            s = r.get("score")
            details = r.get("details", {})
            if isinstance(details, dict) and "combined_score" in details:
                scores.append(float(details["combined_score"]) / 100.0)
            elif s is not None:
                scores.append(float(s))
            elif r.get("status") == "pass" or r.get("passed"):
                scores.append(0.96)
            else:
                scores.append(0.50)
        review_pass = round((sum(scores) / max(len(scores), 1)) * 100.0, 1) if scores else 95.0
    else:
        review_pass = 95.0

    # 4. Readability & Scanability
    readability = _compute_readability(content)

    # 5. 7-Dimension Executive Metrics
    insight_density = _compute_insight_density(content, citations_count)
    strategic_value = _compute_strategic_value(content)
    actionability = _compute_actionability(content)
    narrative_flow = round(min(100.0, max(70.0, format_comp * 0.5 + readability * 0.5)), 1)
    audience_fit = round(min(100.0, max(75.0, review_pass * 0.6 + strategic_value * 0.4)), 1)
    diff_score = round(min(100.0, max(0.0, differentiation_score)), 1)

    # Composite formula weighted across dimensions
    composite = (
        (0.20 * format_comp)
        + (0.15 * citation_cov)
        + (0.15 * review_pass)
        + (0.15 * insight_density)
        + (0.15 * strategic_value)
        + (0.10 * actionability)
        + (0.10 * readability)
    )
    composite = round(min(max(composite, 0.0), 100.0), 1)

    return QualityScoreBreakdown(
        format_compliance=format_comp,
        citation_coverage=citation_cov,
        review_pass_rate=review_pass,
        readability=readability,
        insight_density=insight_density,
        strategic_value=strategic_value,
        actionability=actionability,
        narrative_flow=narrative_flow,
        audience_fit=audience_fit,
        differentiation=diff_score,
        composite_score=composite,
    )
