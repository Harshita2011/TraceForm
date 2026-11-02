"""
# §3.3 Strategic Recommendation Engine (Phase 4)
# Produces concrete, prioritized recommendations (P0/P1/P2) answering "So what?"
# and "What should happen next?" with timelines, owners, ROI framing, and risk mitigations.
"""

from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, Field

from agents.generators.insight_engine import SynthesizedInsights
from schemas.knowledge import KnowledgeExtraction

logger = logging.getLogger(__name__)


class RecommendationItem(BaseModel):
    """A prioritized, actionable executive recommendation."""
    id: str = Field(description="Unique ID, e.g. 'rec_1'")
    priority: str = Field(description="P0 (Immediate / 0-30d) | P1 (Strategic / 30-60d) | P2 (Long-term / 60-90d)")
    title: str = Field(description="Action-oriented title with active verb")
    timeframe: str = Field(description="e.g. '0–30 Days', '30–60 Days', '60–90 Days'")
    owner: str = Field(description="Designated role/team responsible (e.g. 'VP Engineering & Solutions')")
    action_steps: list[str] = Field(description="Concrete operational execution steps")
    expected_roi: str = Field(description="Quantitative expected business/financial return")
    risk_mitigation: str = Field(description="Specific risk mitigated by this action")
    tradeoffs: str = Field(description="Key resource/opportunity tradeoffs acknowledged")


class SynthesizedRecommendations(BaseModel):
    """Comprehensive strategic action plan generated for executive deliverables."""
    decision_statement: str = Field(
        description="Single decisive authorization statement required from executive committee"
    )
    p0_immediate: list[RecommendationItem] = Field(default_factory=list)
    p1_strategic: list[RecommendationItem] = Field(default_factory=list)
    p2_long_term: list[RecommendationItem] = Field(default_factory=list)

    def all_recommendations(self) -> list[RecommendationItem]:
        return self.p0_immediate + self.p1_strategic + self.p2_long_term

    def to_guidance_prompt(self) -> str:
        """Render markdown recommendation blocks for generator prompts."""
        lines = [
            "### STRATEGIC RECOMMENDATIONS & DECISION FRAMEWORK:",
            f"**DECISION REQUIRED:** {self.decision_statement}\n",
            "**PRIORITIZED ACTIONABLE ROADMAP:**"
        ]
        for rec in self.all_recommendations():
            lines.append(
                f"- **{rec.priority} ({rec.timeframe}) - {rec.title}:**\n"
                f"  - *Owner:* {rec.owner}\n"
                f"  - *Execution:* {'; '.join(rec.action_steps)}\n"
                f"  - *Expected Impact / ROI:* {rec.expected_roi}\n"
                f"  - *Risk Mitigation:* {rec.risk_mitigation}"
            )
        return "\n".join(lines)


class RecommendationEngine:
    """
    Strategic Recommendation Engine.
    Synthesizes grounded findings and insights into prioritized P0/P1/P2 executive actions.
    """

    def __init__(self, client: Any = None, model: str | None = None):
        self._client = client
        self._model = model

    def generate_recommendations(
        self,
        context: KnowledgeExtraction,
        insights: SynthesizedInsights | None = None,
    ) -> SynthesizedRecommendations:
        """
        Synthesize prioritized recommendations from extraction and insights.
        """
        # Ask the generator to reason from evidence instead of injecting a
        # fixed retention roadmap with fabricated ROI, owners, and deadlines.
        return SynthesizedRecommendations(
            decision_statement=(
                "Derive any proposed actions from the supplied source facts and user objective. "
                "Label proposals explicitly. Do not claim owners, timelines, ROI, or approvals "
                "unless present in the source. If evidence is insufficient, state the gap."
            ),
        )
