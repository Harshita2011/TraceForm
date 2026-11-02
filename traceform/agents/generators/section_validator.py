"""
# §3.3 Section Validator & Self-Healing Engine
# Verifies that all mandatory blueprint sections are present in generated markdown.
# Includes deterministic self-healing to synthesize any missing required sections.
"""

from __future__ import annotations

import re
from typing import NamedTuple
from agents.generators.blueprints import ArtifactBlueprint
from schemas.knowledge import KnowledgeExtraction


class SectionValidationResult(NamedTuple):
    is_valid: bool
    found_sections: list[str]
    missing_sections: list[str]
    compliance_score: float  # 0.0 to 1.0


def validate_artifact_sections(content: str, blueprint: ArtifactBlueprint) -> SectionValidationResult:
    """
    Verify whether the generated content markdown contains all required sections from the blueprint.
    Uses flexible regex to check for markdown header lines (#, ##, ###, **Header**, etc.).
    """
    if not content:
        return SectionValidationResult(
            is_valid=False,
            found_sections=[],
            missing_sections=list(blueprint.sections),
            compliance_score=0.0,
        )

    found_sections: list[str] = []
    missing_sections: list[str] = []

    content_lower = content.lower()

    for sec in blueprint.sections:
        sec_clean = sec.strip().lower()
        # Also check core title (e.g. "Slide 1" from "Slide 1: Title & Core Thesis")
        sec_prefix = sec_clean.split(":")[0].strip()

        # Check exact header regex, prefix regex, or substring
        pattern = rf"(?:^|\n)(?:[#*_\s\d\.\-:]*){re.escape(sec_clean)}(?:[:*_\s\-]*)(?:\n|$)"
        prefix_pattern = rf"(?:^|\n)(?:[#*_\s\d\.\-:]*){re.escape(sec_prefix)}(?:[:*_\s\-]*)(?:\n|$)"

        if (
            re.search(pattern, content_lower, re.IGNORECASE)
            or sec_clean in content_lower
            or (len(sec_prefix) > 4 and re.search(prefix_pattern, content_lower, re.IGNORECASE))
        ):
            found_sections.append(sec)
        else:
            missing_sections.append(sec)

    total_sections = len(blueprint.sections)
    score = len(found_sections) / max(total_sections, 1)
    is_valid = len(missing_sections) == 0

    return SectionValidationResult(
        is_valid=is_valid,
        found_sections=found_sections,
        missing_sections=missing_sections,
        compliance_score=round(score, 4),
    )


def heal_artifact_sections(
    content: str,
    blueprint: ArtifactBlueprint,
    context: KnowledgeExtraction,
) -> str:
    """
    Self-healing synthesis: If required sections were omitted by the LLM,
    synthesizes well-structured, grounded markdown blocks to ensure 100% section presence.
    """
    val = validate_artifact_sections(content, blueprint)
    if val.is_valid or not val.missing_sections:
        return content

    # Missing evidence must remain explicit; never invent quotes, metrics,
    # contacts, recommendations, or domain-specific claims to fill a heading.
    healed_content = content.rstrip()
    for missing_sec in val.missing_sections:
        healed_content += (
            f"\n\n## {missing_sec}\n"
            "The source does not provide enough information to complete this section."
        )
    return healed_content
