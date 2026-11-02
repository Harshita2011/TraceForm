from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class EvaluationDomain(str, Enum):
    INCIDENT_REPORT = "incident_report"
    POLICY_DOCUMENT = "policy_document"
    NEWS_ARTICLE = "news_article"
    ADVERSARIAL = "adversarial"


class AdversarialAttackType(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    CITATION_FABRICATION = "citation_fabrication"
    COMPLIANCE_OVERRIDE = "compliance_override"
    ROLE_ESCALATION = "role_escalation"
    NONE = "none"


class GroundTruthClaim(BaseModel):
    claim: str
    expected_source_span: str
    must_be_cited: bool = True
    section: Optional[str] = None


class EvaluationSample(BaseModel):
    id: str
    domain: EvaluationDomain
    title: str
    source_document: str
    ground_truth_claims: List[GroundTruthClaim] = Field(default_factory=list)
    expected_style: str = "executive_briefing"
    target_output_types: List[str] = Field(default_factory=lambda: ["executive_briefing", "strategic_memo", "press_release"])
    adversarial_type: AdversarialAttackType = AdversarialAttackType.NONE
    expected_to_fail_compliance: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
