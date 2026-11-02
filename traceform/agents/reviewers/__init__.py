"""
# §3.5 Reviewers package — Style, Fact, Compliance, and StyleQuality (Anti-AI) reviewers.
"""

from agents.reviewers.style import StyleReviewer, STYLE_REVIEWER_VERSION
from agents.reviewers.fact import FactReviewer, FACT_REVIEWER_VERSION
from agents.reviewers.compliance import ComplianceReviewer, COMPLIANCE_REVIEWER_VERSION
from agents.reviewers.style_quality import (
    StyleQualityReviewer,
    STYLE_QUALITY_REVIEWER_VERSION,
    audit_anti_ai_writing,
)

__all__ = [
    "StyleReviewer",
    "STYLE_REVIEWER_VERSION",
    "FactReviewer",
    "FACT_REVIEWER_VERSION",
    "ComplianceReviewer",
    "COMPLIANCE_REVIEWER_VERSION",
    "StyleQualityReviewer",
    "STYLE_QUALITY_REVIEWER_VERSION",
    "audit_anti_ai_writing",
]
