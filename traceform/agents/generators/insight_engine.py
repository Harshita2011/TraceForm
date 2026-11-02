"""
# §3.3 Strategic Insight Extraction Engine (Phase 2 & Phase 7)
# Transforms raw KnowledgeExtraction facts into 1st and 2nd order business implications,
# anomalies, market trends, structural risks, strategic opportunities, and contrarian insights.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from schemas.knowledge import KnowledgeExtraction, Fact

logger = logging.getLogger(__name__)


class InsightItem(BaseModel):
    """A strategic insight derived from ground-truth source evidence."""
    id: str = Field(default="", description="Unique insight ID, e.g. 'ins_1'")
    category: str = Field(
        default="key_finding",
        description="key_finding | anomaly | trend | structural_risk | opportunity | contrarian"
    )
    headline: str = Field(description="Punchy, quantitative executive headline")
    raw_fact: str = Field(description="The underlying factual observation from source")
    strategic_implication: str = Field(description="1st-order operational/financial implication ('So what?')")
    second_order_impact: str = Field(description="2nd-order downstream consequence (valuation, churn, margin, risk)")
    fact_anchor_ids: list[str] = Field(default_factory=list, description="Linked fact IDs from KnowledgeExtraction")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)


class SynthesizedInsights(BaseModel):
    """Full structured intelligence profile synthesized before artifact generation."""
    executive_thesis: str = Field(
        description="Overarching strategic thesis connecting all extracted insights"
    )
    key_findings: list[InsightItem] = Field(default_factory=list)
    anomalies: list[InsightItem] = Field(default_factory=list)
    market_trends: list[InsightItem] = Field(default_factory=list)
    structural_risks: list[InsightItem] = Field(default_factory=list)
    strategic_opportunities: list[InsightItem] = Field(default_factory=list)
    contrarian_insights: list[InsightItem] = Field(default_factory=list)

    def all_insights(self) -> list[InsightItem]:
        return (
            self.key_findings
            + self.anomalies
            + self.market_trends
            + self.structural_risks
            + self.strategic_opportunities
            + self.contrarian_insights
        )

    def to_guidance_prompt(self, max_items_per_category: int = 3) -> str:
        """Render a concise markdown guidance block for generator prompts."""
        lines = [f"### STRATEGIC EXECUTIVE THESIS:\n{self.executive_thesis}\n"]

        if self.key_findings:
            lines.append("### KEY STRATEGIC FINDINGS & IMPLICATIONS:")
            for k in self.key_findings[:max_items_per_category]:
                lines.append(f"- **{k.headline}:** {k.strategic_implication} *(2nd-order: {k.second_order_impact})*")

        if self.anomalies:
            lines.append("\n### CRITICAL ANOMALIES & OPERATIONAL RISKS:")
            for a in self.anomalies[:max_items_per_category]:
                lines.append(f"- **{a.headline}:** {a.strategic_implication}")

        if self.strategic_opportunities:
            lines.append("\n### HIGH-LEVERAGE OPPORTUNITIES:")
            for o in self.strategic_opportunities[:max_items_per_category]:
                lines.append(f"- **{o.headline}:** {o.strategic_implication}")

        if self.contrarian_insights:
            lines.append("\n### CONTRARIAN & THOUGHT LEADERSHIP ANGLES:")
            for c in self.contrarian_insights[:max_items_per_category]:
                lines.append(f"- **{c.headline}:** {c.strategic_implication}")

        return "\n".join(lines)


class InsightEngine:
    """
    Strategic Insight Extraction Engine.
    Processes KnowledgeExtraction into actionable, high-density business intelligence.
    """

    def __init__(self, client: Any = None, model: str | None = None):
        self._client = client
        self._model = model

    def extract_insights(self, context: KnowledgeExtraction) -> SynthesizedInsights:
        """
        Synthesizes strategic insights from KnowledgeExtraction.
        Uses deterministic heuristic modeling with fact implication synthesis.
        """
        # Deterministic guidance may restate evidence, but cannot establish
        # causal business implications that the source never supplied.
        findings = [
            InsightItem(
                id=f"find_{idx + 1}", category="key_finding",
                headline=fact.claim, raw_fact=fact.claim,
                strategic_implication=fact.claim,
                second_order_impact="Not established by the source; assess before drawing conclusions.",
                fact_anchor_ids=[str(getattr(fact, "id", None) or f"f_{idx + 1}")],
            )
            for idx, fact in enumerate(context.facts)
        ]
        return SynthesizedInsights(
            executive_thesis=context.summary or "No source summary available.",
            key_findings=findings,
        )
