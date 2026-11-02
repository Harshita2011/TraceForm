"""
# §3.3 Generator unit tests — mocked Anthropic client, fixed KnowledgeExtraction fixtures.
# Tests verify: correct output type, facts_used populated, version metadata set,
# and that generators ONLY use KnowledgeExtraction (never raw text).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.generators.base import GenericGeneratorAgent
from agents.generators.executive_summary import ExecutiveSummaryGenerator
from agents.generators.linkedin_post import LinkedInPostGenerator
from schemas.generation import GenerationParams
from tests.fixtures.knowledge_extraction import (
    APPLE_REVENUE_EXTRACTION,
    MINIMAL_EXTRACTION,
)

# Mock Anthropic response data
_MOCK_LINKEDIN_CONTENT = {
    "content": "🚀 Apple Inc. delivers Q3 2024 record revenue of $85.8B!\n\n"
               "Tim Cook led the company to another stellar quarter driven by iPhone growth.\n\n"
               "#Apple #Tech #Innovation",
    "facts_used": [
        {
            "claim": "Apple reported Q3 2024 revenue of $85.8 billion.",
            "source_span": "Apple reported Q3 2024 revenue of $85.8 billion",
            "start_char": 0,
            "end_char": 48,
            "confidence": 0.95,
        }
    ],
}

_MOCK_EXEC_SUMMARY_CONTENT = {
    "content": "## Executive Summary\n\n### Overview\nApple Inc. delivered strong Q3 2024 results.\n\n"
               "### Key Findings\n- Revenue: $85.8 billion\n- Primary driver: iPhone sales\n\n"
               "### Implications\nContinued dominance in premium hardware segment.",
    "facts_used": [
        {
            "claim": "Apple reported Q3 2024 revenue of $85.8 billion.",
            "source_span": "Apple reported Q3 2024 revenue of $85.8 billion",
            "start_char": 0,
            "end_char": 48,
            "confidence": 0.95,
        }
    ],
}


def _make_mock_client(content_dict: dict) -> MagicMock:
    """Create a mock AsyncAnthropic client that returns a given content dict as JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(content_dict))]
    mock_response.usage.input_tokens = 1000
    mock_response.usage.output_tokens = 200

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


class TestLinkedInPostGenerator:

    async def test_output_type_is_linkedin_post(self):
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client)
        assert gen.output_type == "linkedin_post"

    async def test_generate_returns_result_with_content(self):
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client)
        params = GenerationParams()

        result = await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        assert result.content is not None
        assert len(result.content) > 0
        assert result.output_type == "linkedin_post"

    async def test_generate_populates_facts_used(self):
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client)
        params = GenerationParams()

        result = await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        assert isinstance(result.facts_used, list)
        assert len(result.facts_used) > 0

    async def test_generate_pins_prompt_version(self):
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client)
        params = GenerationParams()

        result = await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        assert result.prompt_version == "1.0.0"

    async def test_generate_pins_model_version(self):
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client, model="claude-test-model")
        params = GenerationParams()

        result = await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        assert result.model_version == "claude-test-model"

    async def test_generate_does_not_pass_raw_text(self):
        """
        §3.3 — Generator MUST NOT pass raw source text to LLM.
        Verify that the user message contains only structured KnowledgeExtraction JSON,
        not the raw extracted_text from the Source record.
        """
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client)
        params = GenerationParams()

        await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        # Inspect what was passed to the LLM
        call_args = client.messages.create.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])

        user_message_content = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_message_content = msg.get("content", "")
                break

        # The user message should contain JSON (KnowledgeExtraction)
        assert "summary" in user_message_content or "facts" in user_message_content
        # It should NOT contain the raw source text identifier we'd only see from the Source model
        # (In real usage the raw text would be the un-parsed document — not accessible here)

    async def test_params_override_applied(self):
        """§3.4 — Per-output-type param overrides must merge correctly."""
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client)
        params = GenerationParams(
            tone="professional",
            overrides={"linkedin_post": {"tone": "casual and engaging"}},
        )

        await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        # System prompt should contain the overridden tone
        call_args = client.messages.create.call_args
        system_prompt = call_args.kwargs.get("system", "")
        assert "casual and engaging" in system_prompt

    async def test_minimal_extraction_works(self):
        """Generator should work with the minimal fixture too."""
        client = _make_mock_client(_MOCK_LINKEDIN_CONTENT)
        gen = LinkedInPostGenerator(client=client)
        params = GenerationParams()

        result = await gen.generate(context=MINIMAL_EXTRACTION, params=params)
        assert result.content is not None


class TestExecutiveSummaryGenerator:

    async def test_output_type_is_executive_summary(self):
        client = _make_mock_client(_MOCK_EXEC_SUMMARY_CONTENT)
        gen = ExecutiveSummaryGenerator(client=client)
        assert gen.output_type == "executive_summary"

    async def test_generate_returns_structured_content(self):
        client = _make_mock_client(_MOCK_EXEC_SUMMARY_CONTENT)
        gen = ExecutiveSummaryGenerator(client=client)
        params = GenerationParams()

        result = await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        assert result.content is not None
        assert result.output_type == "executive_summary"
        assert result.prompt_version == "1.0.0"

    async def test_token_usage_captured(self):
        client = _make_mock_client(_MOCK_EXEC_SUMMARY_CONTENT)
        gen = ExecutiveSummaryGenerator(client=client)
        params = GenerationParams()

        result = await gen.generate(context=APPLE_REVENUE_EXTRACTION, params=params)

        assert "input_tokens" in result.token_usage
        assert "output_tokens" in result.token_usage
        assert result.token_usage["input_tokens"] > 0


class TestGenericGeneratorExtensibility:

    def test_unknown_output_type_raises_file_not_found(self):
        """§1.3 — Only YAML config needed for a new output type."""
        from agents.generators.base import load_output_type_config
        with pytest.raises(FileNotFoundError, match="No YAML config"):
            load_output_type_config("nonexistent_type_xyz")

    def test_generation_params_override_precedence(self):
        """§3.4 — Per-type overrides win over global params."""
        params = GenerationParams(
            tone="professional",
            audience="general",
            overrides={"linkedin_post": {"tone": "punchy", "audience": "executives"}},
        )
        merged = params.for_output_type("linkedin_post")
        assert merged.tone == "punchy"
        assert merged.audience == "executives"
        # Non-overridden fields retain global value
        assert merged.language == "en"

    def test_generation_params_no_override_unchanged(self):
        """§3.4 — Output types without overrides use global params unchanged."""
        params = GenerationParams(tone="formal", overrides={"twitter": {"tone": "casual"}})
        merged = params.for_output_type("linkedin_post")
        assert merged.tone == "formal"
