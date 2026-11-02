"""
# §3.5 StyleQualityReviewer (Phase 6 — Anti-AI Writing Detection & Editorial Quality)
# Detects and penalizes AI clichés, generic openings, repetitive transitions,
# excessive bullet dumping, and robotic boilerplate.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from agents.base import ReviewerAgent
from agents.generators.blueprints import get_blueprint
from agents.llm import call_llm, create_llm_client, get_default_model
from schemas.generation import GenerationParams
from schemas.knowledge import KnowledgeExtraction
from schemas.review import ReviewResult

logger = logging.getLogger(__name__)

STYLE_QUALITY_REVIEWER_VERSION = "2.0.0"

# Explicit Anti-AI Cliché Patterns to scrub/penalize
ANTI_AI_PATTERNS = [
    (r"\bin today'?s (?:rapidly evolving|fast-paced|dynamic|ever-changing) (?:landscape|world|environment|market)\b", "Generic throat-clearing opening cliché"),
    (r"\bin the fast-paced world of\b", "Generic cliché opening"),
    (r"\bit is (?:important|crucial|essential|worth|pivotal|paramount) to (?:note|remember|consider|highlight)\b", "Robotic passive observation"),
    (r"\bthis highlights the importance of\b", "Passive truism cliché"),
    (r"\bin conclusion,?\b", "Robotic school-essay transition"),
    (r"\bdelve(?:s|d|ing)? into\b", "Overused AI vocabulary"),
    (r"\btapestry of\b", "Overused AI metaphor"),
    (r"\bbeacon of\b", "Overused AI metaphor"),
    (r"\btestament to\b", "Overused AI cliché"),
    (r"\bgame-?changing\b", "Marketing hype buzzword"),
    (r"\bgroundbreaking\b", "Unsubstantiated marketing buzzword"),
    (r"\brevolutionize\b", "Overused marketing hype"),
    (r"\bsynergistic\b", "Generic corporate buzzword"),
]


class AntiAIAuditResult(BaseModel):
    passed: bool
    quality_score: float = Field(ge=0.0, le=100.0)
    detected_cliches: list[dict[str, str]] = Field(default_factory=list)
    generic_opening_flagged: bool = False
    repetitive_transitions_flagged: bool = False
    excessive_bulleting_flagged: bool = False
    editorial_suggestions: list[str] = Field(default_factory=list)


def audit_anti_ai_writing(content: str, output_type: str = "executive_briefing") -> AntiAIAuditResult:
    """
    Perform deterministic static regex & structural audit for Anti-AI writing violations.
    """
    if not content:
        return AntiAIAuditResult(passed=False, quality_score=0.0, editorial_suggestions=["Content is empty."])

    detected_cliches: list[dict[str, str]] = []
    text_lower = content.lower()

    for pattern, reason in ANTI_AI_PATTERNS:
        matches = re.findall(pattern, text_lower)
        if matches:
            for m in set(matches):
                detected_cliches.append({"phrase": m, "reason": reason})

    # Check for generic throat-clearing openings in the first 250 characters
    opening_slice = text_lower[:250]
    generic_opening = any(
        phrase in opening_slice
        for phrase in [
            "in today's",
            "in the era of",
            "as we move into",
            "with the rapid rise of",
            "in the ever-evolving",
        ]
    )

    # Check repetitive transitions
    transitions = re.findall(r"(?:^|\n)(?:Furthermore|Moreover|Additionally|Consequently|In addition),?\s+", content)
    repetitive_transitions = len(transitions) >= 2

    # Check excessive bulleting: if >70% of lines are bullets in an executive memo
    lines = [line.strip() for line in content.split("\n") if line.strip()]
    bullet_lines = [l for l in lines if l.startswith(("-", "*", "•", "1.", "2.", "3.", "4."))]
    excessive_bulleting = (len(lines) > 6 and (len(bullet_lines) / len(lines)) > 0.80 and output_type in ["executive_briefing", "press_release"])

    # Compute quality deduction
    penalties = (
        len(detected_cliches) * 12.0
        + (25.0 if generic_opening else 0.0)
        + (15.0 if repetitive_transitions else 0.0)
        + (15.0 if excessive_bulleting else 0.0)
    )
    score = max(0.0, min(100.0, 100.0 - penalties))
    passed = score >= 75.0 and len(detected_cliches) == 0 and not generic_opening

    suggestions: list[str] = []
    if detected_cliches:
        suggestions.append(f"Remove AI clichés: {', '.join(c['phrase'] for c in detected_cliches[:3])}.")
    if generic_opening:
        suggestions.append("Replace generic throat-clearing opening with direct bottom-line insight (BLUF).")
    if repetitive_transitions:
        suggestions.append("Vary sentence transitions; eliminate repetitive 'Furthermore/Moreover' connectors.")
    if excessive_bulleting:
        suggestions.append("Convert excessive bullet list into structured, narrative prose.")

    return AntiAIAuditResult(
        passed=passed,
        quality_score=round(score, 1),
        detected_cliches=detected_cliches,
        generic_opening_flagged=generic_opening,
        repetitive_transitions_flagged=repetitive_transitions,
        excessive_bulleting_flagged=excessive_bulleting,
        editorial_suggestions=suggestions,
    )


class StyleQualityReviewer(ReviewerAgent):
    """
    §3.5 / Phase 6 — Anti-AI Writing & Editorial Style Quality Reviewer.
    Evaluates human-like writing quality, insight depth, narrative flow, and eliminates AI boilerplate.
    """

    def __init__(
        self,
        client: Any = None,
        model: str | None = None,
        reviewer_version: str = STYLE_QUALITY_REVIEWER_VERSION,
    ):
        self._client = client
        self._model = model or get_default_model()
        self._version = reviewer_version

    @property
    def version(self) -> str:
        return self._version

    async def review(
        self,
        artifact_content: str,
        context: KnowledgeExtraction,
        params: GenerationParams,
    ) -> ReviewResult:
        """
        Execute deterministic Anti-AI audit combined with LLM editorial evaluation.
        """
        output_type = params.output_type or "executive_briefing"
        bp = get_blueprint(output_type)

        # 1. Deterministic Anti-AI static check
        audit = audit_anti_ai_writing(artifact_content, output_type=output_type)

        # 2. LLM-as-Judge editorial quality evaluation
        system_prompt = (
            "You are a world-class executive editor and communications director. "
            "You evaluate whether the content reads like it was written by a senior partner at McKinsey, "
            "a seasoned Fortune 500 Chief of Staff, or an elite tech journalist rather than an AI.\n\n"
            "Penalize: generic summaries, lack of 'So what?' implications, repetitive transitions, and AI tropes.\n"
            "Reward: punchy openings, quantitative implications, clear narrative flow, and high insight density.\n\n"
            "Respond ONLY with a valid JSON object in this format:\n"
            "{\n"
            '  "passed": true,\n'
            '  "quality_score": 92.0,\n'
            '  "human_writing_score": 95.0,\n'
            '  "insight_density_score": 90.0,\n'
            '  "reasoning": "Detailed assessment of voice, narrative cadence, and strategic value.",\n'
            '  "issues": ["Issue 1", "Issue 2"],\n'
            '  "editorial_suggestions": ["Suggestion 1"]\n'
            "}"
        )

        user_content = (
            f"Artifact Format: {output_type} ({bp.role} for {bp.audience})\n"
            f"Reading Depth: {bp.reading_depth}\n"
            f"Target Tone: {bp.tone_profile}\n"
            f"Static Audit Passed: {audit.passed} (Score: {audit.quality_score})\n"
            f"Static Clichés Found: {[c['phrase'] for c in audit.detected_cliches]}\n\n"
            "--- ARTIFACT CONTENT ---\n"
            f"{artifact_content}\n\n"
            "Evaluate editorial quality and return valid JSON."
        )

        client = self._client or create_llm_client()

        try:
            raw_text, token_usage = await call_llm(
                client=client,
                model=self._model,
                system_prompt=system_prompt,
                user_content=user_content,
                max_tokens=1024,
                json_mode=True,
            )
            data = self._parse_json(raw_text)
            if not isinstance(data.get("passed"), bool) or not isinstance(data.get("quality_score"), (int, float)):
                raise ValueError("Editorial judge did not return a measured result")
            llm_passed = data["passed"]
            llm_score = float(data["quality_score"])
            if not 0 <= llm_score <= 100:
                raise ValueError("Editorial quality score is outside its valid range")
            combined_score = round(0.40 * audit.quality_score + 0.60 * llm_score, 1)
            passed = audit.passed and llm_passed and combined_score >= 70.0

            details = {
                "passed": passed,
                "combined_score": combined_score,
                "static_audit": audit.model_dump(),
                "llm_score": llm_score,
                "human_writing_score": data.get("human_writing_score"),
                "insight_density_score": data.get("insight_density_score"),
                "reasoning": data.get("reasoning", "Editorial evaluation completed."),
                "issues": audit.editorial_suggestions + data.get("issues", []),
                "token_usage": token_usage,
            }
        except Exception as exc:
            logger.warning("StyleQualityReviewer LLM evaluation fallback: %s", exc)
            passed = audit.passed
            details = {
                "passed": passed,
                "combined_score": audit.quality_score,
                "static_audit": audit.model_dump(),
                "reasoning": f"Static audit completed (Score: {audit.quality_score}). LLM judge skipped ({exc}).",
                "issues": audit.editorial_suggestions,
                "token_usage": {"input_tokens": 0, "output_tokens": 0},
            }

        return ReviewResult(
            reviewer_name="style_quality_reviewer",
            passed=passed,
            details=details,
            reviewer_version=self._version,
        )

    def _parse_json(self, raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)
