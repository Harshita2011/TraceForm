"""
# §3.3 Multi-Dimensional Differentiation Validator & ArtifactDifferentiationEngine
#
# Prevents semantic, structural, and narrative bleed across generated artifacts.
# Calculates pairwise cross-artifact similarity across 5 dimensions:
#   1. Semantic Cosine Similarity (TF-IDF / Term Frequency)
#   2. Lexical Jaccard Overlap (Vocabulary Redundancy)
#   3. Structural & Header Overlap (Section Hierarchy)
#   4. Opening & Conclusion Paragraph Similarity
#   5. Recommendation / Action Item Overlap
#
# Rules:
#   - Artifact Differentiation Score = 100 - (Composite Similarity * 100)
#   - 90-100: Excellent Differentiation
#   - 80-89:  Acceptable Differentiation
#   - Below 80: Flagged Generic -> Triggers Automated Regeneration
#   - Verified Delivery Threshold >= 85
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pydantic import BaseModel, Field
from agents.generators.blueprints import ArtifactBlueprint, get_blueprint

MAX_ALLOWED_SIMILARITY: float = 0.55
DIFFERENTIATION_PASS_THRESHOLD: float = 85.0


class PairwiseSimilarity(BaseModel):
    artifact_type_a: str
    artifact_type_b: str
    semantic_score: float
    lexical_score: float
    structural_score: float
    opening_similarity: float = 0.0
    conclusion_similarity: float = 0.0
    recommendation_similarity: float = 0.0
    composite_similarity: float
    differentiation_score: float = 95.0  # 0-100
    exceeds_threshold: bool
    overlap_notes: list[str] = Field(default_factory=list)


class ArtifactUniquenessScore(BaseModel):
    artifact_type: str
    uniqueness_score: float  # 0 to 100 (Differentiation Score)
    is_generic: bool         # True if score < 80
    max_pairwise_similarity: float
    most_similar_artifact: str | None = None
    role: str
    audience: str
    purpose: str
    writing_style: str
    flagged_reasons: list[str] = Field(default_factory=list)


class DifferentiationReport(BaseModel):
    is_differentiated: bool
    max_similarity: float
    min_differentiation_score: float = 95.0
    threshold: float = MAX_ALLOWED_SIMILARITY
    flagged_pairs: list[PairwiseSimilarity] = Field(default_factory=list)
    uniqueness_scores: dict[str, ArtifactUniquenessScore] = Field(default_factory=dict)
    regeneration_recommendations: dict[str, str] = Field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercased alpha words (ignoring common stopwords)."""
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    stopwords = {
        "the", "and", "for", "that", "this", "with", "from", "are", "have",
        "has", "been", "will", "would", "should", "could", "about", "into",
        "which", "their", "there", "they", "what", "when", "where", "who"
    }
    return [w for w in words if w not in stopwords]


def _extract_headings(text: str) -> set[str]:
    """Extract markdown header titles from text."""
    headings = re.findall(r"(?:^|\n)#{1,6}\s*(.+)", text)
    if not headings:
        headings = re.findall(r"(?:^|\n)\*\*(.+?)\*\*", text)
    return {h.strip().lower() for h in headings if len(h.strip()) > 2}


def _extract_paragraphs(text: str) -> list[str]:
    """Extract non-heading body paragraphs."""
    raw = text.split("\n\n")
    cleaned = []
    for p in raw:
        stripped = p.strip()
        if stripped and not stripped.startswith("#") and len(stripped) > 20:
            cleaned.append(stripped)
    return cleaned


def _calculate_tf_idf_cosine(text_a: str, text_b: str) -> float:
    """Compute TF-IDF / Term-Frequency Cosine Similarity between two texts."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0

    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)

    all_vocab = set(counts_a.keys()).union(set(counts_b.keys()))
    dot_product = sum(counts_a.get(w, 0) * counts_b.get(w, 0) for w in all_vocab)
    norm_a = math.sqrt(sum(v ** 2 for v in counts_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in counts_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _calculate_lexical_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity of distinct word tokens."""
    tokens_a = set(_tokenize(text_a))
    tokens_b = set(_tokenize(text_b))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def _calculate_structural_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity of extracted markdown headings."""
    heads_a = _extract_headings(text_a)
    heads_b = _extract_headings(text_b)
    if not heads_a or not heads_b:
        return 0.0
    intersection = heads_a.intersection(heads_b)
    union = heads_a.union(heads_b)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def _calculate_paragraph_boundary_similarity(text_a: str, text_b: str) -> tuple[float, float]:
    """Calculate opening and conclusion paragraph similarity."""
    paras_a = _extract_paragraphs(text_a)
    paras_b = _extract_paragraphs(text_b)

    opening_sim = 0.0
    conclusion_sim = 0.0

    if paras_a and paras_b:
        opening_sim = _calculate_tf_idf_cosine(paras_a[0], paras_b[0])
        conclusion_sim = _calculate_tf_idf_cosine(paras_a[-1], paras_b[-1])

    return opening_sim, conclusion_sim


def _extract_recommendation_text(text: str) -> str:
    """Extract recommendation or action sections if present."""
    match = re.search(r"(?:recommendations?|actionable takeaways?|next steps?|actions?)([\s\S]+?)(?:##|$)", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def compute_pairwise_similarity(
    type_a: str,
    text_a: str,
    type_b: str,
    text_b: str,
    threshold: float = MAX_ALLOWED_SIMILARITY,
) -> PairwiseSimilarity:
    """Compute composite similarity across 5 key dimensions."""
    sem = _calculate_tf_idf_cosine(text_a, text_b)
    lex = _calculate_lexical_similarity(text_a, text_b)
    struct = _calculate_structural_similarity(text_a, text_b)
    opening_sim, conclusion_sim = _calculate_paragraph_boundary_similarity(text_a, text_b)

    recs_a = _extract_recommendation_text(text_a)
    recs_b = _extract_recommendation_text(text_b)
    rec_sim = _calculate_tf_idf_cosine(recs_a, recs_b) if (recs_a and recs_b) else 0.0

    # 5-Dimensional Weighted composite similarity
    composite = (
        0.30 * sem +
        0.20 * lex +
        0.20 * struct +
        0.15 * opening_sim +
        0.15 * rec_sim
    )

    # Differentiation Score = 100 - (composite * 100)
    diff_score = max(0.0, min(100.0, 100.0 - (composite * 100.0)))
    exceeds = composite > threshold

    notes: list[str] = []
    if sem >= 0.65:
        notes.append(f"High semantic overlap ({sem:.2f}): Shared phrasing and vocabulary.")
    if struct >= 0.50:
        notes.append(f"High structural overlap ({struct:.2f}): Shared markdown section headers.")
    if opening_sim >= 0.60:
        notes.append(f"Similar opening paragraphs ({opening_sim:.2f}): Lead sentences lack distinct persona.")
    if rec_sim >= 0.60:
        notes.append(f"Similar recommendation items ({rec_sim:.2f}): Action points overlap excessively.")

    return PairwiseSimilarity(
        artifact_type_a=type_a,
        artifact_type_b=type_b,
        semantic_score=round(sem, 3),
        lexical_score=round(lex, 3),
        structural_score=round(struct, 3),
        opening_similarity=round(opening_sim, 3),
        conclusion_similarity=round(conclusion_sim, 3),
        recommendation_similarity=round(rec_sim, 3),
        composite_similarity=round(composite, 3),
        differentiation_score=round(diff_score, 1),
        exceeds_threshold=exceeds,
        overlap_notes=notes,
    )


def calculate_artifact_uniqueness(
    artifact_type: str,
    content: str,
    other_artifacts: dict[str, str],
    threshold: float = MAX_ALLOWED_SIMILARITY,
) -> ArtifactUniquenessScore:
    """Calculate uniqueness & differentiation score for a single artifact."""
    bp = get_blueprint(artifact_type)
    if not other_artifacts:
        return ArtifactUniquenessScore(
            artifact_type=artifact_type,
            uniqueness_score=100.0,
            is_generic=False,
            max_pairwise_similarity=0.0,
            most_similar_artifact=None,
            role=bp.role,
            audience=bp.audience,
            purpose=bp.purpose,
            writing_style=bp.writing_style,
            flagged_reasons=[],
        )

    sims = [
        compute_pairwise_similarity(artifact_type, content, other_t, other_c, threshold)
        for other_t, other_c in other_artifacts.items()
        if other_t != artifact_type
    ]
    if not sims:
        return ArtifactUniquenessScore(
            artifact_type=artifact_type,
            uniqueness_score=100.0,
            is_generic=False,
            max_pairwise_similarity=0.0,
            most_similar_artifact=None,
            role=bp.role,
            audience=bp.audience,
            purpose=bp.purpose,
            writing_style=bp.writing_style,
            flagged_reasons=[],
        )

    worst_pair = max(sims, key=lambda s: s.composite_similarity)
    max_pair_sim = worst_pair.composite_similarity
    other_type = worst_pair.artifact_type_b if worst_pair.artifact_type_a == artifact_type else worst_pair.artifact_type_a

    u_score = worst_pair.differentiation_score
    is_generic = u_score < 80.0

    flagged: list[str] = []
    if u_score < DIFFERENTIATION_PASS_THRESHOLD:
        flagged.append(f"Differentiation score ({u_score:.1f}/100) below target threshold {DIFFERENTIATION_PASS_THRESHOLD}.")
    if worst_pair.overlap_notes:
        flagged.extend(worst_pair.overlap_notes)

    return ArtifactUniquenessScore(
        artifact_type=artifact_type,
        uniqueness_score=round(u_score, 1),
        is_generic=is_generic,
        max_pairwise_similarity=round(max_pair_sim, 3),
        most_similar_artifact=other_type,
        role=bp.role,
        audience=bp.audience,
        purpose=bp.purpose,
        writing_style=bp.writing_style,
        flagged_reasons=flagged,
    )


def validate_artifact_batch_differentiation(
    artifacts: dict[str, str],
    threshold: float = MAX_ALLOWED_SIMILARITY,
) -> DifferentiationReport:
    """
    Validates an entire batch of generated artifacts against cross-format similarity.
    """
    types = list(artifacts.keys())
    flagged: list[PairwiseSimilarity] = []
    max_sim = 0.0
    min_diff = 100.0
    regen_recs: dict[str, str] = {}

    for i in range(len(types)):
        for j in range(i + 1, len(types)):
            t_a, t_b = types[i], types[j]
            pair = compute_pairwise_similarity(t_a, artifacts[t_a], t_b, artifacts[t_b], threshold)
            if pair.composite_similarity > max_sim:
                max_sim = pair.composite_similarity
            if pair.differentiation_score < min_diff:
                min_diff = pair.differentiation_score

            if pair.exceeds_threshold:
                flagged.append(pair)
                bp_a = get_blueprint(t_a)
                bp_b = get_blueprint(t_b)
                regen_recs[t_b] = (
                    f"Excessive overlap with {t_a} ({pair.composite_similarity:.2f}). "
                    f"Shift strictly to {bp_b.writing_style} for {bp_b.audience}. "
                    f"Avoid phrasing: {bp_a.role} conventions."
                )

    uniqueness_map: dict[str, ArtifactUniquenessScore] = {}
    for t, content in artifacts.items():
        other = {k: v for k, v in artifacts.items() if k != t}
        uniqueness_map[t] = calculate_artifact_uniqueness(t, content, other, threshold)

    is_diff = len(flagged) == 0

    return DifferentiationReport(
        is_differentiated=is_diff,
        max_similarity=round(max_sim, 3),
        min_differentiation_score=round(min_diff, 1),
        threshold=threshold,
        flagged_pairs=flagged,
        uniqueness_scores=uniqueness_map,
        regeneration_recommendations=regen_recs,
    )


# Backward-compatible alias
validate_artifact_differentiation = validate_artifact_batch_differentiation


class ArtifactDifferentiationEngine:
    """Class wrapper for Artifact Differentiation validation."""
    def __init__(self, threshold: float = MAX_ALLOWED_SIMILARITY):
        self.threshold = threshold

    def evaluate(self, artifacts: dict[str, str]) -> DifferentiationReport:
        return validate_artifact_batch_differentiation(artifacts, self.threshold)

    def validate_batch(self, artifacts: dict[str, str]) -> DifferentiationReport:
        return validate_artifact_batch_differentiation(artifacts, self.threshold)

    def calculate_uniqueness(self, artifact_type: str, content: str, other_artifacts: dict[str, str]) -> ArtifactUniquenessScore:
        return calculate_artifact_uniqueness(artifact_type, content, other_artifacts, self.threshold)

    def compute_pairwise(self, type_a: str, text_a: str, type_b: str, text_b: str) -> PairwiseSimilarity:
        return compute_pairwise_similarity(type_a, text_a, type_b, text_b, self.threshold)
