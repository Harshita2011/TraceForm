import logging
import re
from typing import Any, List, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProvenanceClaimCheck(BaseModel):
    claim: str
    has_source_anchor: bool
    source_span: str = ""
    confidence: float = 1.0
    status: str = "VERIFIED"  # "VERIFIED" | "UNVERIFIED" | "HALLUCINATION"


class ProvenanceValidationReport(BaseModel):
    artifact_id: str = ""
    total_claims: int = 0
    verified_claims: int = 0
    unsupported_claims: int = 0
    hallucination_rate: float = 0.0
    citation_coverage: float = 1.0
    is_valid: bool = True
    claim_checks: List[ProvenanceClaimCheck] = Field(default_factory=list)


def validate_provenance_integrity(
    artifact_content: str,
    facts_used: List[dict[str, Any]],
    source_text: str,
) -> ProvenanceValidationReport:
    """
    §6I — Provenance Integrity Validator.
    Verifies that every factual claim in the generated content is anchored to a
    ground-truth source span in the source text.
    If a claim exists without verifiable source coordinates, it is flagged as UNVERIFIED.
    """
    if not facts_used:
        # Check if text contains numerical/factual assertions without any facts_used
        has_assertions = bool(re.search(r"\b\d+(\.\d+)?%?|\$\d+", artifact_content))
        if has_assertions:
            return ProvenanceValidationReport(
                total_claims=1,
                verified_claims=0,
                unsupported_claims=1,
                hallucination_rate=1.0,
                citation_coverage=0.0,
                is_valid=False,
                claim_checks=[
                    ProvenanceClaimCheck(
                        claim=artifact_content[:100],
                        has_source_anchor=False,
                        status="UNVERIFIED",
                    )
                ],
            )
        return ProvenanceValidationReport(
            total_claims=0,
            verified_claims=0,
            unsupported_claims=0,
            hallucination_rate=0.0,
            citation_coverage=1.0,
            is_valid=True,
        )

    checks: List[ProvenanceClaimCheck] = []
    total = len(facts_used)
    verified = 0
    unsupported = 0

    clean_source = source_text.lower().replace("\n", " ")

    for fact in facts_used:
        claim_text = str(fact.get("claim") or fact.get("generated_claim") or "")
        span_text = str(fact.get("source_span") or fact.get("span") or "")

        # Verify if span appears in the source document
        clean_span = span_text.lower().replace("\n", " ").strip()

        # Also check start/end char bounds if provided
        start_char = fact.get("start_char")
        end_char = fact.get("end_char")

        has_anchor = False
        if clean_span and clean_span in clean_source:
            has_anchor = True
        elif start_char is not None and end_char is not None and 0 <= start_char < len(source_text):
            sliced = source_text[start_char:end_char].strip().lower()
            if sliced:
                has_anchor = True

        if has_anchor:
            verified += 1
            checks.append(
                ProvenanceClaimCheck(
                    claim=claim_text,
                    has_source_anchor=True,
                    source_span=span_text,
                    status="VERIFIED",
                )
            )
        else:
            unsupported += 1
            checks.append(
                ProvenanceClaimCheck(
                    claim=claim_text,
                    has_source_anchor=False,
                    source_span=span_text,
                    status="UNVERIFIED",
                )
            )

    hallucination_rate = round(unsupported / total, 4) if total > 0 else 0.0
    citation_coverage = round(verified / total, 4) if total > 0 else 1.0
    is_valid = unsupported == 0

    return ProvenanceValidationReport(
        total_claims=total,
        verified_claims=verified,
        unsupported_claims=unsupported,
        hallucination_rate=hallucination_rate,
        citation_coverage=citation_coverage,
        is_valid=is_valid,
        claim_checks=checks,
    )
