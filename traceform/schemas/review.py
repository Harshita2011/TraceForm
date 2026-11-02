"""
# §3.5 Review Layer — Pydantic schema for reviewer results.
"""

from pydantic import BaseModel


class ReviewResult(BaseModel):
    """§3.5 — Output of any reviewer agent. Reviewers are side-effect-free checks."""
    reviewer_name: str
    passed: bool
    details: dict
    reviewer_version: str
