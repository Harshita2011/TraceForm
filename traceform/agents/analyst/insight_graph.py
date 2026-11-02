"""
# Artifact Intelligence Layer — Evidence Graph & Insight Graph Engine
#
# Transforms flat KnowledgeExtraction facts into a multi-tiered graph:
#   1. Evidence Nodes (1st-Order Facts & Grounded Coordinates)
#   2. Insight Nodes (2nd-Order Strategic Implications & "So What?" Analyses)
#   3. Decision Vectors (Actionable Decisions, Trade-Offs, and Timelines)
#   4. Audience Relevance Mapping (C-Suite vs Engineering vs Media vs Board)
"""

from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, Field

from schemas.knowledge import KnowledgeExtraction, Fact, Relationship


class EvidenceNode(BaseModel):
    """1st-Order Operational Fact anchored to exact document coordinates."""
    id: str
    claim: str
    source_span: str
    start_char: int
    end_char: int
    confidence: float
    entities_involved: list[str] = Field(default_factory=list)
    category: Literal["metric", "finding", "statement", "constraint", "event"] = "finding"


class InsightNode(BaseModel):
    """2nd-Order Strategic Implication derived from one or more Evidence Nodes."""
    id: str
    core_insight: str
    strategic_implication: str  # "So what?"
    evidence_ids: list[str] = Field(default_factory=list)
    impact_level: Literal["critical", "high", "medium", "low"] = "high"
    target_audiences: list[str] = Field(default_factory=list)
    market_context: str = ""


class DecisionVector(BaseModel):
    """Actionable decision point or recommended intervention."""
    id: str
    decision_prompt: str
    recommended_action: str
    risk_of_inaction: str
    urgency: Literal["immediate", "near_term", "strategic"] = "near_term"
    supported_by_insights: list[str] = Field(default_factory=list)


class EvidenceAndInsightGraph(BaseModel):
    """
    Unified Evidence & Insight Graph powering all downstream Artifact Planners.
    Replaces flat summary ingestion with multi-dimensional reasoning inputs.
    """
    domain: str
    summary_context: str
    evidence_nodes: list[EvidenceNode] = Field(default_factory=list)
    insight_nodes: list[InsightNode] = Field(default_factory=list)
    decision_vectors: list[DecisionVector] = Field(default_factory=list)
    key_relationships: list[Relationship] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)

    def get_evidence_by_id(self, evidence_id: str) -> EvidenceNode | None:
        for node in self.evidence_nodes:
            if node.id == evidence_id:
                return node
        return None

    def get_insights_for_audience(self, audience_keyword: str) -> list[InsightNode]:
        kw = audience_keyword.lower()
        matches = [
            node for node in self.insight_nodes
            if any(kw in aud.lower() for aud in node.target_audiences)
        ]
        return matches if matches else self.insight_nodes

    def to_planner_context(self, audience: str, role: str) -> str:
        """Render a formatted reasoning brief for an artifact planner."""
        relevant_insights = self.get_insights_for_audience(audience)

        evidence_lines = [
            f"- [{node.id}] {node.claim} (Span: '{node.source_span[:60]}...')"
            for node in self.evidence_nodes[:8]
        ]

        insight_lines = [
            f"- [{node.id}] {node.core_insight} | Strategic Impact: {node.strategic_implication}"
            for node in relevant_insights[:6]
        ]

        decision_lines = [
            f"- [{d.id}] Decision: {d.decision_prompt} -> Action: {d.recommended_action} (Risk: {d.risk_of_inaction})"
            for d in self.decision_vectors[:4]
        ]

        return (
            f"=== EVIDENCE & INSIGHT GRAPH CONTEXT ===\n"
            f"Domain: {self.domain.upper()}\n"
            f"Context: {self.summary_context}\n\n"
            f"1ST-ORDER EVIDENCE NODES ({len(self.evidence_nodes)}):\n" + "\n".join(evidence_lines) + "\n\n"
            f"2ND-ORDER STRATEGIC INSIGHTS ({len(relevant_insights)}):\n" + "\n".join(insight_lines) + "\n\n"
            f"ACTIONABLE DECISION VECTORS ({len(self.decision_vectors)}):\n" + "\n".join(decision_lines)
        )


def _categorize_fact(claim: str) -> Literal["metric", "finding", "statement", "constraint", "event"]:
    if re.search(r"\b(\d+[%$€£]?|\$\d+|\d+\.\d+)\b", claim):
        return "metric"
    if any(w in claim.lower() for w in ["must", "require", "limit", "prohibit", "deadline"]):
        return "constraint"
    if any(w in claim.lower() for w in ["launched", "announced", "occurred", "released", "breached"]):
        return "event"
    if any(w in claim.lower() for w in ["shows", "indicates", "discovered", "identified", "found"]):
        return "finding"
    return "statement"


def _derive_strategic_implication(claim: str, domain: str) -> tuple[str, str, list[str]]:
    """Derive core insight, 2nd-order implication, and audience relevance."""
    claim_lower = claim.lower()

    if any(w in claim_lower for w in ["increase", "growth", "improved", "accelerate", "expand"]):
        core = f"Positive acceleration detected in {domain} metrics"
        implication = "Presents immediate scaling or expansion opportunities requiring capital and resource allocation."
        audiences = ["CEO / Executive Leadership", "Board of Directors", "Investors", "Founders"]
    elif any(w in claim_lower for w in ["risk", "vulnerability", "failure", "breach", "incident", "unauthorized", "penalty", "compromise"]):
        core = f"Operational or security exposure identified in {domain}"
        implication = "Requires proactive governance remediation and immediate containment to avoid brand and financial liability."
        audiences = ["Board of Directors", "Governance Committee", "Technical Leads", "Legal", "CEO / Executive Leadership"]
    elif any(w in claim_lower for w in ["cost", "spend", "budget", "expense", "capital"]):
        core = f"Financial capital efficiency vector in {domain}"
        implication = "Demands tighter unit economic governance and prioritization of highest ROI initiatives."
        audiences = ["CEO / C-Suite", "Leadership Team", "Finance & Operations", "Board of Directors"]
    else:
        core = f"Key operational baseline established for {domain}"
        implication = "Provides decision-grade foundation for strategic roadmap planning and resource realignment."
        audiences = ["Executive Leadership", "Technical Leads", "Subscribers", "Public"]

    return core, implication, audiences


def build_evidence_insight_graph(extraction: KnowledgeExtraction) -> EvidenceAndInsightGraph:
    """
    Builds a complete EvidenceAndInsightGraph from extracted knowledge facts and relationships.
    """
    all_entities = (
        extraction.entities.organizations +
        extraction.entities.people +
        extraction.entities.products +
        extraction.entities.locations
    )

    evidence_nodes: list[EvidenceNode] = []
    insight_nodes: list[InsightNode] = []
    decision_vectors: list[DecisionVector] = []

    for idx, fact in enumerate(extraction.facts):
        ev_id = f"EV-{idx + 1:02d}"
        involved = [e for e in all_entities if e.lower() in fact.claim.lower()]
        cat = _categorize_fact(fact.claim)

        ev_node = EvidenceNode(
            id=ev_id,
            claim=fact.claim,
            source_span=fact.source_span,
            start_char=fact.start_char,
            end_char=fact.end_char,
            confidence=fact.confidence,
            entities_involved=involved,
            category=cat,
        )
        evidence_nodes.append(ev_node)

        # Derive 2nd-order strategic insight
        core_ins, imp, target_auds = _derive_strategic_implication(fact.claim, extraction.domain)
        ins_id = f"INS-{idx + 1:02d}"

        insight_node = InsightNode(
            id=ins_id,
            core_insight=f"{core_ins}: {fact.claim[:80]}",
            strategic_implication=imp,
            evidence_ids=[ev_id],
            impact_level="critical" if cat in ("metric", "constraint") else "high",
            target_audiences=target_auds,
            market_context=f"Domain: {extraction.domain}. Source Tone: {extraction.source_tone}.",
        )
        insight_nodes.append(insight_node)

    # Construct actionable decision vectors
    for idx, ins in enumerate(insight_nodes[:4]):
        d_id = f"DEC-{idx + 1:02d}"
        decision_vectors.append(DecisionVector(
            id=d_id,
            decision_prompt=f"How should leadership respond to {ins.core_insight}?",
            recommended_action=f"Execute targeted initiative addressing: {ins.strategic_implication}",
            risk_of_inaction="Loss of competitive velocity or unaddressed operational drag.",
            urgency="immediate" if ins.impact_level == "critical" else "near_term",
            supported_by_insights=[ins.id],
        ))

    return EvidenceAndInsightGraph(
        domain=extraction.domain,
        summary_context=extraction.summary,
        evidence_nodes=evidence_nodes,
        insight_nodes=insight_nodes,
        decision_vectors=decision_vectors,
        key_relationships=extraction.relationships,
        organizations=extraction.entities.organizations,
        people=extraction.entities.people,
        products=extraction.entities.products,
    )
