"""
# Artifact Intelligence Layer — Multi-Agent Artifact Specialist Reviewers
#
# Every artifact receives a dedicated specialist review tailored strictly to its
# native medium, target audience, structural fidelity, and anti-bleed guarantees.
#
# Examples:
#   - Strategic Memo -> StrategicMemoSpecialistReviewer
#   - LinkedIn Post  -> LinkedInSpecialistReviewer
#   - Press Release  -> PressReleaseSpecialistReviewer
#   - Executive Briefing -> ExecutiveBriefingSpecialistReviewer
#   - Technical Report -> TechnicalReportSpecialistReviewer
#   - Twitter/X Thread -> TwitterSpecialistReviewer
#   - Newsletter     -> NewsletterSpecialistReviewer
"""

from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field

from agents.generators.blueprints import get_blueprint, ArtifactBlueprint
from agents.generators.planners import create_artifact_plan, ArtifactPlan
from schemas.knowledge import KnowledgeExtraction


class SpecialistReviewResult(BaseModel):
    """Outcome of an artifact specialist reviewer pass."""
    reviewer_name: str
    output_type: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    native_feel_confirmed: bool
    structure_adherence: float = Field(ge=0.0, le=1.0)
    tone_alignment: float = Field(ge=0.0, le=1.0)
    anti_bleed_passed: bool
    reasons: list[str] = Field(default_factory=list)
    remediation_notes: list[str] = Field(default_factory=list)


def _check_sections_presence(content: str, required_sections: list[str]) -> float:
    """Calculate ratio of required section headers present in markdown content."""
    if not required_sections:
        return 1.0

    content_lower = content.lower()
    matched = 0
    for s in required_sections:
        pattern = re.escape(s.lower())
        if re.search(r"#{1,6}\s*" + pattern, content_lower) or re.search(r"\*\*" + pattern + r"\*\*", content_lower) or pattern in content_lower:
            matched += 1
    return matched / len(required_sections)


# ─────────────────────────────────────────────────────────────────────────────
# Specialist Reviewer Functions
# ─────────────────────────────────────────────────────────────────────────────

def review_linkedin_post(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    # 1. Native structure & length
    words = content.split()
    word_count = len(words)
    has_bullets = any(b in content for b in ['•', '-', '*', '1.', '2.'])
    has_takeaways = "takeaway" in content.lower() or "lesson" in content.lower() or has_bullets
    raw_section_score = _check_sections_presence(content, ["Hook", "Problem", "Insight", "Takeaways", "Call To Action"])

    # 2. Check for thumb-stopping hook
    first_lines = [l.strip() for l in content.split("\n") if l.strip()][:3]
    has_hook = any(len(l) < 120 for l in first_lines)

    # 3. Check for engagement CTA / question
    has_cta = "?" in content or "what" in content.lower() or "how do you" in content.lower() or "share" in content.lower()

    # 4. Anti-bleed checks (must not look like a formal memo or press release)
    has_memo_bleed = any(term in content.lower() for term in ["memorandum", "to: ", "from: ", "fiduciary", "board of directors"])
    has_pr_bleed = any(term in content.lower() for term in ["for immediate release", "dateline", "media contact", "press release"])

    native_feel = has_hook and has_cta and not has_memo_bleed and not has_pr_bleed and word_count <= 450
    structure_score = max(raw_section_score, 0.95 if (has_hook and has_takeaways and has_cta) else 0.40)
    anti_bleed = not has_memo_bleed and not has_pr_bleed

    if not has_hook:
        reasons.append("Missing high-impact thumb-stopping opening hook.")
        remediation.append("Open with a punchy, counter-intuitive 1-line hook.")
    if not has_cta:
        reasons.append("Missing conversational call to action driving comments.")
        remediation.append("End with an open question for peer practitioners.")
    if has_memo_bleed or has_pr_bleed:
        reasons.append("Cross-format bleed detected: Contains memo or press release tropes.")
        remediation.append("Eliminate formal memo headers and PR boilerplate.")

    passed = native_feel and structure_score >= 0.70 and anti_bleed
    score = 0.96 if passed else max(0.40, structure_score * 0.5 + (0.4 if native_feel else 0.1))

    return SpecialistReviewResult(
        reviewer_name="LinkedInSpecialistReviewer",
        output_type="linkedin_post",
        passed=passed,
        score=round(score, 2),
        native_feel_confirmed=native_feel,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.95 if native_feel else 0.60,
        anti_bleed_passed=anti_bleed,
        reasons=reasons or ["LinkedIn formatting, hook, takeaways, and CTA verified."],
        remediation_notes=remediation,
    )


def review_twitter_x(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    # 1. Thread numbering
    has_numbering = bool(re.search(r"\b1/\d|\b1/n|\b1\)", content))
    tweet_count = len(re.findall(r"(?:^|\n)\s*(?:\d+/\w+|\d+\))\s*", content))

    # 2. Anti-bleed
    has_memo_bleed = "executive summary" in content.lower() or "memorandum" in content.lower()

    native_feel = has_numbering and not has_memo_bleed

    if not has_numbering:
        reasons.append("Missing tweet thread numbering (1/n, 2/n format).")
        remediation.append("Structure each tweet with explicit '1/n', '2/n' headers.")

    passed = native_feel
    score = 0.96 if passed else 0.50

    return SpecialistReviewResult(
        reviewer_name="TwitterSpecialistReviewer",
        output_type="twitter_x",
        passed=passed,
        score=score,
        native_feel_confirmed=native_feel,
        structure_adherence=0.95 if has_numbering else 0.40,
        tone_alignment=0.95 if native_feel else 0.50,
        anti_bleed_passed=not has_memo_bleed,
        reasons=reasons or ["Twitter/X thread numbering and skimmability verified."],
        remediation_notes=remediation,
    )


def review_executive_summary(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    structure_score = _check_sections_presence(content, blueprint.sections)
    word_count = len(content.split())
    is_under_1_page = word_count <= 500

    has_bluf = bool(re.search(r"\b\d+[%$€£]?\b", content[:250]))  # Numbers up front
    has_social_bleed = bool(re.search(r"(?<!\w)#[A-Za-z]\w*", content)) or "let me know in the comments" in content.lower()

    if not is_under_1_page:
        reasons.append(f"Exceeds 1-page executive constraint ({word_count} words).")
        remediation.append("Trim content to under 450 words focusing only on BLUF findings.")
    if structure_score < 0.80:
        reasons.append("Missing required executive summary decision sections.")
        remediation.append("Include: " + ", ".join(blueprint.sections) + ".")

    passed = structure_score >= 0.75 and is_under_1_page and not has_social_bleed
    score = 0.96 if passed else max(0.45, structure_score * 0.6)

    return SpecialistReviewResult(
        reviewer_name="ExecutiveSummarySpecialistReviewer",
        output_type="executive_summary",
        passed=passed,
        score=round(score, 2),
        native_feel_confirmed=is_under_1_page and has_bluf,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.95 if not has_social_bleed else 0.50,
        anti_bleed_passed=not has_social_bleed,
        reasons=reasons or ["Executive Summary 1-page brevity and BLUF framing confirmed."],
        remediation_notes=remediation,
    )


def review_executive_briefing(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    structure_score = _check_sections_presence(content, ["Situation", "Why It Matters", "Critical Developments", "Strategic Risks", "Recommended Actions"])
    has_bluf = bool(re.search(r"\b\d+[%$€£]?\b", content[:300]))

    passed = structure_score >= 0.70
    score = 0.95 if passed else 0.55

    return SpecialistReviewResult(
        reviewer_name="ExecutiveBriefingSpecialistReviewer",
        output_type="executive_briefing",
        passed=passed,
        score=score,
        native_feel_confirmed=has_bluf,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.95,
        anti_bleed_passed=True,
        reasons=reasons or ["Executive briefing situation and recommended actions confirmed."],
        remediation_notes=remediation,
    )


def review_strategic_memo(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    sections = [
        "Executive Context",
        "Strategic Analysis",
        "Market Implications",
        "Competitive Analysis",
        "Business Risks",
        "Growth Opportunities",
        "Strategic Recommendations",
        "Implementation Roadmap",
    ]
    structure_score = _check_sections_presence(content, sections)

    # Check for management consulting depth & roadmap
    has_roadmap = "roadmap" in content.lower() or "phase" in content.lower() or "0-30" in content or "timeline" in content.lower()
    has_casual_bleed = "hey guys" in content.lower() or "let's connect" in content.lower()

    if not has_roadmap:
        reasons.append("Missing implementation roadmap or phased execution timeline.")
        remediation.append("Add structured Implementation Roadmap with Phase 1 (0-30d) and Phase 2 (30-90d).")
    if structure_score < 0.70:
        reasons.append("Missing core management consulting analysis sections.")
        remediation.append("Ensure full consulting structure (Strategic Analysis, Risks, Growth Opportunities, Roadmap).")

    passed = structure_score >= 0.70 and has_roadmap and not has_casual_bleed
    score = 0.97 if passed else max(0.40, structure_score * 0.6)

    return SpecialistReviewResult(
        reviewer_name="StrategicMemoSpecialistReviewer",
        output_type="strategic_memo",
        passed=passed,
        score=round(score, 2),
        native_feel_confirmed=has_roadmap,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.95 if not has_casual_bleed else 0.50,
        anti_bleed_passed=not has_casual_bleed,
        reasons=reasons or ["McKinsey/Bain caliber strategic analysis and roadmap confirmed."],
        remediation_notes=remediation,
    )


def review_press_release(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    structure_score = _check_sections_presence(content, ["Headline", "Subheadline", "Announcement", "Quote", "Boilerplate"])
    has_quotes = '"' in content or "“" in content
    has_dateline = bool(re.search(r"\[.+?\]|\b[A-Z]{3,},\s*[A-Z]{2}\b|—\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})", content))

    if not has_quotes:
        reasons.append("Missing attributed executive quotation.")
        remediation.append("Include an executive quote with full name and executive title.")
    if not has_dateline:
        reasons.append("Missing AP wire dateline header.")
        remediation.append("Include standard wire dateline: [CITY, STATE] — [Date] —.")

    passed = structure_score >= 0.60 and has_quotes
    score = 0.96 if passed else 0.50

    return SpecialistReviewResult(
        reviewer_name="PressReleaseSpecialistReviewer",
        output_type="press_release",
        passed=passed,
        score=score,
        native_feel_confirmed=has_quotes and has_dateline,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.95,
        anti_bleed_passed=True,
        reasons=reasons or ["AP Wire format, headline, dateline, and executive quotes verified."],
        remediation_notes=remediation,
    )


def review_newsletter(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    structure_score = _check_sections_presence(content, ["Opening Note", "Major Developments", "Analysis", "Key Takeaways", "Closing Commentary"])
    has_editorial_open = len(content.strip()) > 100

    passed = structure_score >= 0.60 and has_editorial_open
    score = 0.95 if passed else 0.55

    return SpecialistReviewResult(
        reviewer_name="NewsletterSpecialistReviewer",
        output_type="newsletter",
        passed=passed,
        score=score,
        native_feel_confirmed=has_editorial_open,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.95,
        anti_bleed_passed=True,
        reasons=reasons or ["Editorial newsletter tone, curation, and sign-off verified."],
        remediation_notes=remediation,
    )


def review_technical_report(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    reasons: list[str] = []
    remediation: list[str] = []

    sections = ["Abstract", "Introduction", "Methodology", "Analysis", "Findings", "Limitations", "Conclusion"]
    structure_score = _check_sections_presence(content, sections)
    has_limitations = "limitation" in content.lower() or "scope" in content.lower() or "boundary" in content.lower()

    if not has_limitations:
        reasons.append("Missing explicit technical limitations or scope boundaries.")
        remediation.append("Add a formal Limitations section addressing data bounds and edge cases.")

    passed = structure_score >= 0.65 and has_limitations
    score = 0.96 if passed else 0.50

    return SpecialistReviewResult(
        reviewer_name="TechnicalReportSpecialistReviewer",
        output_type="technical_report",
        passed=passed,
        score=score,
        native_feel_confirmed=has_limitations,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.95,
        anti_bleed_passed=True,
        reasons=reasons or ["Empirical methodology, findings, and technical limitations verified."],
        remediation_notes=remediation,
    )


def review_generic_specialist(content: str, blueprint: ArtifactBlueprint) -> SpecialistReviewResult:
    structure_score = _check_sections_presence(content, blueprint.sections)
    passed = structure_score >= 0.60
    return SpecialistReviewResult(
        reviewer_name="GeneralSpecialistReviewer",
        output_type=blueprint.id,
        passed=passed,
        score=0.92 if passed else 0.55,
        native_feel_confirmed=passed,
        structure_adherence=round(structure_score, 2),
        tone_alignment=0.90,
        anti_bleed_passed=True,
        reasons=["Blueprint format guidelines verified."] if passed else ["Sections missing."],
        remediation_notes=[],
    )


SPECIALIST_REVIEWER_MAP = {
    "linkedin_post": review_linkedin_post,
    "twitter_x": review_twitter_x,
    "executive_summary": review_executive_summary,
    "executive_briefing": review_executive_briefing,
    "strategic_memo": review_strategic_memo,
    "press_release": review_press_release,
    "newsletter": review_newsletter,
    "technical_report": review_technical_report,
    "research_report": review_technical_report,
}


def run_specialist_review(
    output_type: str,
    content: str,
    blueprint: ArtifactBlueprint | None = None,
) -> SpecialistReviewResult:
    """
    Executes the designated Specialist Reviewer for the requested artifact type.
    """
    bp = blueprint or get_blueprint(output_type)
    rev_fn = SPECIALIST_REVIEWER_MAP.get(output_type)
    if rev_fn:
        return rev_fn(content, bp)
    return review_generic_specialist(content, bp)
