"""
# §5 Abstract Base Classes — Generator and Reviewer interfaces.
# These are the ONLY way agents receive source-derived content.
# Generators receive a KnowledgeExtraction object — NEVER raw source text.
# Reviewers receive read-only artifact copies — they are side-effect-free.
"""

from abc import ABC, abstractmethod

from schemas.knowledge import KnowledgeExtraction
from schemas.generation import GenerationParams
from schemas.review import ReviewResult


class GeneratorArtifactResult:
    """Intermediate result from a generator before DB persistence."""
    def __init__(
        self,
        output_type: str,
        content: str,
        facts_used: list[dict],
        prompt_version: str,
        model_version: str,
        token_usage: dict,
        key_insights: list[str] | None = None,
        blueprint_version: str | None = None,
        purpose: str | None = None,
        target_audience: str | None = None,
        decision_focus: str | None = None,
        format_meta: dict | None = None,
    ):
        self.output_type = output_type
        self.content = content
        self.facts_used = facts_used
        self.prompt_version = prompt_version
        self.model_version = model_version
        self.token_usage = token_usage
        self.key_insights = key_insights or []
        self.blueprint_version = blueprint_version or f"{output_type}:v1"
        self.purpose = purpose or "Verified Intelligence"
        self.target_audience = target_audience or "Stakeholders"
        self.decision_focus = decision_focus or "Strategic Context"
        self.format_meta = format_meta or {}


class GeneratorAgent(ABC):
    """
    §5 — Abstract interface for all Generator Agents.

    CRITICAL: generate() receives a KnowledgeExtraction object only.
    Raw source text must NEVER be passed to or re-inserted into a generator's prompt.
    This is enforced at the type-signature level — there is no parameter for raw text.
    """

    @abstractmethod
    async def generate(
        self,
        context: KnowledgeExtraction,
        params: GenerationParams,
        correction_notes: list[str] | str | None = None,
    ) -> GeneratorArtifactResult:
        """
        Generate an artifact from structured knowledge extraction.

        Args:
            context: Structured knowledge extracted by the Analyst Agent — never raw source text.
            params: Generation parameters (audience, tone, etc.) merged with per-type overrides.
            correction_notes: Optional specific failing claims from Fact Review to correct in targeted regeneration.

        Returns:
            GeneratorArtifactResult with content, facts_used, and version metadata.
        """
        ...

    @property
    @abstractmethod
    def output_type(self) -> str:
        """The YAML config key for this output type (e.g. 'linkedin_post')."""
        ...


class ReviewerAgent(ABC):
    """
    §3.5 — Abstract interface for all Reviewer Agents.

    Reviewers receive read-only data — they must not mutate the artifact or call other reviewers.
    No reviewer may trigger side effects beyond returning a ReviewResult.
    """

    @abstractmethod
    async def review(
        self,
        artifact_content: str,
        context: KnowledgeExtraction,
        params: GenerationParams,
    ) -> ReviewResult:
        """
        Review a generated artifact for compliance with a specific criterion.

        Args:
            artifact_content: The generated text content (read-only copy).
            context: The KnowledgeExtraction that was used to generate the artifact.
            params: The GenerationParams used for this artifact.

        Returns:
            ReviewResult with passed bool, details, and reviewer_version.
        """
        ...
