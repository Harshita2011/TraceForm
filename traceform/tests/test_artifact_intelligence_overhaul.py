"""
# Test Suite: TraceForm Artifact Intelligence Overhaul
#
# Validates:
#   1. Evidence Graph & Insight Graph Engine
#   2. Dedicated Artifact Planners & Audience Modeling
#   3. Multi-Agent Specialist Reviewers
#   4. 5-Dimensional Cross-Artifact Differentiation Engine (Score >= 85)
#   5. Anti-Similarity and Anti-Bleed Guarantees
"""

import pytest
from agents.analyst.insight_graph import build_evidence_insight_graph, EvidenceAndInsightGraph
from agents.generators.planners import (
    create_artifact_plan,
    plan_linkedin_post,
    plan_strategic_memo,
    plan_press_release,
    plan_executive_briefing,
    plan_executive_summary,
    plan_technical_report,
    plan_twitter_x,
    plan_newsletter,
)
from agents.reviewers.specialist import (
    run_specialist_review,
    review_strategic_memo,
    review_linkedin_post,
    review_press_release,
    review_twitter_x,
    review_executive_summary,
)
from agents.generators.differentiation import (
    compute_pairwise_similarity,
    calculate_artifact_uniqueness,
    validate_artifact_batch_differentiation,
)
from agents.generators.blueprints import get_blueprint
from schemas.knowledge import KnowledgeExtraction, Fact, Entities, Relationship


@pytest.fixture
def sample_extraction() -> KnowledgeExtraction:
    return KnowledgeExtraction(
        summary="Acme Corp announced an enterprise security incident affecting 15,000 customer accounts with an estimated $2.4M remediation cost.",
        entities=Entities(
            organizations=["Acme Corp", "CloudShield Security"],
            people=["Jane Doe", "John Smith"],
            locations=["San Francisco", "London"],
            products=["Acme Cloud Gateway", "ShieldProtect v2"],
        ),
        facts=[
            Fact(
                claim="Acme Corp suffered an unauthorized access incident on October 14.",
                source_span="unauthorized access incident on October 14",
                start_char=10,
                end_char=52,
                confidence=0.98,
            ),
            Fact(
                claim="Total customer accounts impacted reached 15,000 records.",
                source_span="impacted reached 15,000 records",
                start_char=60,
                end_char=91,
                confidence=0.95,
            ),
            Fact(
                claim="Estimated remediation and compliance penalty costs total $2.4M.",
                source_span="penalty costs total $2.4M",
                start_char=100,
                end_char=125,
                confidence=0.92,
            ),
            Fact(
                claim="Acme Corp deployed CloudShield Security patches within 4 hours.",
                source_span="deployed CloudShield Security patches within 4 hours",
                start_char=140,
                end_char=192,
                confidence=0.99,
            ),
        ],
        relationships=[
            Relationship(source="Acme Corp", relation="remediated_by", target="CloudShield Security")
        ],
        domain="Cybersecurity & Enterprise Governance",
        source_tone="Objective / Incident Disclosure",
        sensitivity="internal",
        sensitivity_source="operator",
        sensitivity_confidence=0.95,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Evidence Graph & Insight Graph Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_evidence_and_insight_graph_builder(sample_extraction):
    graph = build_evidence_insight_graph(sample_extraction)

    assert len(graph.evidence_nodes) == 4
    assert len(graph.insight_nodes) == 4
    assert len(graph.decision_vectors) >= 2

    # Check that 2nd-order strategic implications are derived
    insights = graph.get_insights_for_audience("Board of Directors")
    assert len(insights) > 0
    assert any("remediation" in i.strategic_implication.lower() or "exposure" in i.core_insight.lower() for i in insights)

    # Check planner context rendering
    context_str = graph.to_planner_context(audience="CEO", role="Chief of Staff")
    assert "EVIDENCE & INSIGHT GRAPH CONTEXT" in context_str
    assert "1ST-ORDER EVIDENCE NODES" in context_str
    assert "2ND-ORDER STRATEGIC INSIGHTS" in context_str


# ─────────────────────────────────────────────────────────────────────────────
# 2. Artifact Planners Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_planners_generate_distinct_models(sample_extraction):
    graph = build_evidence_insight_graph(sample_extraction)

    li_plan = create_artifact_plan("linkedin_post", graph)
    sm_plan = create_artifact_plan("strategic_memo", graph)
    pr_plan = create_artifact_plan("press_release", graph)
    tw_plan = create_artifact_plan("twitter_x", graph)
    tr_plan = create_artifact_plan("technical_report", graph)

    # Validate distinct personas and primary reader questions
    assert li_plan.audience_model.persona != sm_plan.audience_model.persona
    assert li_plan.audience_model.primary_question != pr_plan.audience_model.primary_question
    assert sm_plan.writing_blueprint.writing_style != tw_plan.writing_blueprint.writing_style

    # Validate distinct native structures
    assert "Hook" in li_plan.native_structure
    assert "Executive Context" in sm_plan.native_structure
    assert "Headline" in pr_plan.native_structure
    assert "1/n Hook" in tw_plan.native_structure
    assert "Abstract" in tr_plan.native_structure

    # Check prompt instruction generation
    prompt_text = sm_plan.render_prompt_instructions()
    assert "STRATEGIC_MEMO" in prompt_text
    assert "Executive Context" in prompt_text


# ─────────────────────────────────────────────────────────────────────────────
# 3. Multi-Agent Specialist Reviewer Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_strategic_memo_specialist_reviewer():
    valid_memo = """## Executive Context
Acme Corp experienced a critical operational incident on October 14.

## Strategic Analysis
The core vulnerability stemmed from unpatched gateway endpoints.

## Market Implications
Enterprise competitors may leverage this incident to capture market share.

## Competitive Analysis
CloudShield deployment provides an asymmetric defense moat.

## Business Risks
Downside risk includes customer churn and $2.4M remediation liabilities.

## Growth Opportunities
Positioning security-first SLA contracts unlocks enterprise expansion.

## Strategic Recommendations
1. Mandate automated security patch cycles across all clusters.
2. Establish a dedicated Board Governance Risk Committee.

## Implementation Roadmap
- Phase 1 (0-30d): Immediate audit and patch verification.
- Phase 2 (30-90d): Comprehensive SOC2 Type II reassessment.
"""
    res = run_specialist_review("strategic_memo", valid_memo)
    assert res.passed is True
    assert res.score >= 0.90
    assert res.native_feel_confirmed is True


def test_linkedin_specialist_reviewer():
    valid_linkedin = """15,000 accounts compromised. $2.4M in potential fallout.

Here is the truth most executives miss about security incidents:

The real cost isn't the penalty. It's the operational trust treadmill.

When Acme Corp faced a breach on Oct 14, they didn't hide it.
They patched within 4 hours and transparently notified users.

3 Operating Takeaways:
• Speed of disclosure dictates brand recovery.
• Unit economics suffer when governance is reactive.
• Incident playbooks must be rehearsed quarterly.

How does your organization handle proactive security disclosure? Let's discuss below.

#Cybersecurity #Leadership #Operations #SaaS"""

    res = run_specialist_review("linkedin_post", valid_linkedin)
    assert res.passed is True
    assert res.score >= 0.90
    assert res.native_feel_confirmed is True


def test_press_release_specialist_reviewer():
    valid_pr = """## Headline
Acme Corp Unveils Comprehensive Enterprise Security Upgrade Following Swift Incident Remediation

## Subheadline
Organization Deploys CloudShield Infrastructure Within Four Hours, Protecting Over 15,000 Customer Environments

## Announcement
SAN FRANCISCO — October 15, 2026 — Acme Corp today announced the completion of an enterprise-wide infrastructure patch following an unauthorized access event.

## Supporting Details
The incident, which occurred on October 14, was identified and contained within four hours with zero data exfiltration.

## Executive Quote
"Our highest priority is safeguarding our customer ecosystem," said Jane Doe, Chief Executive Officer of Acme Corp. "Our swift four-hour containment demonstrates our commitment to transparency."

## Additional Information
Customer accounts remain fully operational with enhanced multi-factor authentication.

## Company Boilerplate
About Acme Corp: Acme Corp is a global leader in enterprise cloud infrastructure."""

    res = run_specialist_review("press_release", valid_pr)
    assert res.passed is True
    assert res.score >= 0.90


def test_twitter_x_specialist_reviewer():
    valid_twitter = """1/n A breach hits 15,000 accounts. Most companies stall. Acme Corp patched in 4 hours.

2/n Context: An unauthorized access incident occurred on Oct 14 affecting $2.4M in potential liabilities.

3/n Core Insight: Speed is your only real moat. A 4-hour remediation window saved millions in brand equity.

4/n Evidence: Deploying CloudShield security stopped exfiltration before customer data was moved.

5/n Actionable Takeaway: Build automated patch triggers before you need them. Rehearse response times quarterly."""

    res = run_specialist_review("twitter_x", valid_twitter)
    assert res.passed is True
    assert res.score >= 0.90


# ─────────────────────────────────────────────────────────────────────────────
# 4. 5-Dimensional Cross-Artifact Differentiation Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_diverse_artifacts_achieve_high_differentiation_score():
    memo_text = """## Executive Context
Fiduciary governance requires immediate strategic mitigation.

## Strategic Analysis
Capital expenditure of $2.4M must be reallocated to security moats.

## Implementation Roadmap
Phase 1 (0-30d): Board audit and risk committee formation."""

    linkedin_text = """15,000 accounts compromised. Here is why speed matters.

Most founders think breaches are purely technical failures. They aren't.

3 Takeaways:
• Playbooks win.
• Transparency builds trust.
• Rehearse responses.

What is your take? #Leadership #Startups"""

    pr_text = """## Headline
Acme Corp Announces Complete Remediation of Infrastructure Security

## Announcement
SAN FRANCISCO — Oct 15 — Acme Corp today issued an official statement regarding enterprise system integrity.

## Executive Quote
"We responded immediately," stated Jane Doe, CEO."""

    report_text = """## Abstract
An empirical investigation into 4-hour patch latency across 15,000 distributed customer nodes.

## Methodology
Telemetry logs were sampled across a 24-hour observation window.

## Limitations
Scope bounded to cloud gateway endpoints."""

    batch = {
        "strategic_memo": memo_text,
        "linkedin_post": linkedin_text,
        "press_release": pr_text,
        "technical_report": report_text,
    }

    report = validate_artifact_batch_differentiation(batch)
    assert report.is_differentiated is True
    assert report.min_differentiation_score >= 85.0
    assert report.max_similarity < 0.45


def test_identical_summaries_are_flagged_generic():
    summary_1 = "Acme Corp had a breach affecting 15000 accounts with 2.4M in remediation costs."
    summary_2 = "Acme Corp had a breach affecting 15000 accounts with 2.4M in remediation costs."

    batch = {
        "doc_a": summary_1,
        "doc_b": summary_2,
    }

    report = validate_artifact_batch_differentiation(batch)
    assert report.is_differentiated is False
    assert report.min_differentiation_score < 80.0
    assert len(report.flagged_pairs) > 0
