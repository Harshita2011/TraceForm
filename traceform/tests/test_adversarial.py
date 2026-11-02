"""
# §3.1.1 Adversarial input fixture tests.

SECURITY-CRITICAL: Verifies that sources containing prompt injection attempts
are treated as inert data throughout the pipeline — never executed as instructions.

This test DOES NOT call the real LLM. It mocks the Anthropic client and verifies:
1. The adversarial text is placed in the user turn, not the system prompt.
2. The Analyst Agent's prompt builder structurally prevents system-prompt injection.
3. A correctly-behaving LLM response treats the injection as a quoted fact.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.analyst.agent import AnalystAgent
from agents.analyst.prompt import build_analyst_prompt
from db.models import Source
from schemas.enums import SensitivityLevel, SensitivitySource
from tests.fixtures.adversarial_sources import (
    CLEAN_SOURCE,
    INJECTION_ATTEMPT_SOURCE,
    INJECTION_FACT_KEYWORDS,
)


def _make_analyst_source(text: str) -> Source:
    """Create a mock Source ORM object for testing."""
    source = MagicMock(spec=Source)
    source.id = "test-source-id"
    source.extracted_text = text
    source.sensitivity = SensitivityLevel.PUBLIC
    source.sensitivity_source = SensitivitySource.CLASSIFIER
    source.sensitivity_confidence = 0.5
    return source


def _make_mock_analyst_client(extraction_data: dict) -> MagicMock:
    """Create a mock Anthropic client that returns a given KnowledgeExtraction dict."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(extraction_data))]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 300

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


# A well-behaved LLM response to the injection source —
# it REPORTS the injection attempt as a fact, does NOT act on it.
_INJECTION_HANDLED_RESPONSE = {
    "summary": "A business report that also contains text attempting prompt injection.",
    "entities": {"organizations": [], "people": [], "locations": [], "products": []},
    "facts": [
        {
            "claim": "The source contains text that appears to attempt instruction injection: 'ignore previous instructions'.",
            "source_span": "ignore previous instructions",
            "start_char": INJECTION_ATTEMPT_SOURCE.find("ignore previous instructions"),
            "end_char": INJECTION_ATTEMPT_SOURCE.find("ignore previous instructions") + len("ignore previous instructions"),
            "confidence": 0.99,
        },
        {
            "claim": "Revenue was $100 million for the quarter.",
            "source_span": "Revenue was $100 million for the quarter.",
            "start_char": INJECTION_ATTEMPT_SOURCE.find("Revenue was $100 million"),
            "end_char": INJECTION_ATTEMPT_SOURCE.find("Revenue was $100 million") + len("Revenue was $100 million for the quarter."),
            "confidence": 0.95,
        },
    ],
    "relationships": [],
    "domain": "finance",
    "source_tone": "formal",
    "sensitivity": "public",
    "sensitivity_source": "classifier",
    "sensitivity_confidence": 0.5,
}


class TestAdversarialInputHandling:

    def test_adversarial_text_in_user_turn_not_system(self):
        """
        §3.1.1 — CRITICAL: Source text must appear in user turn only, not the system prompt.
        The system prompt MAY reference adversarial keywords as EXAMPLES in its security instructions.
        What it must NEVER contain is the actual SOURCE TEXT itself.
        """
        prompt = build_analyst_prompt(INJECTION_ATTEMPT_SOURCE)

        # Source-unique content (not mentioned in the system prompt as examples)
        # Check that these specific strings from the source are in user turn, not system
        source_unique_phrases = [
            "Revenue was $100 million for the quarter",
            "Operating profit margin improved to 15%",
            "The company employs 5,000 people",
        ]
        for phrase in source_unique_phrases:
            assert phrase not in prompt.system, (
                f"Source-unique phrase '{phrase}' leaked into system prompt! §3.1.1 violation."
            )
            assert phrase in prompt.messages[0]["content"], (
                f"Phrase '{phrase}' missing from user turn."
            )

        # The source text as a whole must be in the user turn
        assert INJECTION_ATTEMPT_SOURCE in prompt.messages[0]["content"]

    def test_system_prompt_integrity_unchanged(self):
        """System prompt should be identical regardless of source content."""
        prompt_clean = build_analyst_prompt(CLEAN_SOURCE)
        prompt_adversarial = build_analyst_prompt(INJECTION_ATTEMPT_SOURCE)

        # System prompts must be identical — source content doesn't affect instructions
        assert prompt_clean.system == prompt_adversarial.system, (
            "System prompt changed based on source content — this is a §3.1.1 violation."
        )

    async def test_analyst_agent_treats_injection_as_inert_data(self):
        """
        §3.1.1 — The Analyst Agent must treat injection text as a fact to report,
        not as an instruction to execute.
        """
        mock_client = _make_mock_analyst_client(_INJECTION_HANDLED_RESPONSE)
        agent = AnalystAgent(client=mock_client)
        source = _make_analyst_source(INJECTION_ATTEMPT_SOURCE)

        extraction, usage = await agent.extract(source)

        # The extraction should contain a fact ABOUT the injection attempt
        injection_fact = next(
            (f for f in extraction.facts if "inject" in f.claim.lower() or "ignore" in f.claim.lower()),
            None,
        )
        assert injection_fact is not None, (
            "Analyst should report the injection attempt as a quoted fact, not execute it."
        )

        # Verify the injection text was not executed (the extraction should be a normal struct)
        assert extraction.summary is not None
        assert extraction.domain is not None

    async def test_analyst_agent_call_uses_correct_message_structure(self):
        """Verify the Anthropic API is called with system and messages as separate params."""
        mock_client = _make_mock_analyst_client(_INJECTION_HANDLED_RESPONSE)
        agent = AnalystAgent(client=mock_client)
        source = _make_analyst_source(INJECTION_ATTEMPT_SOURCE)

        await agent.extract(source)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        # system must be a separate param, not embedded in messages
        assert "system" in call_kwargs
        assert "messages" in call_kwargs

        # Source-unique content (not mentioned in the system prompt) must NOT appear in system param
        source_unique_phrases = [
            "Revenue was $100 million for the quarter",
            "Operating profit margin improved to 15%",
        ]
        for phrase in source_unique_phrases:
            assert phrase not in call_kwargs["system"], (
                f"Source-unique phrase '{phrase}' found in 'system' API param — §3.1.1 violation."
            )

    def test_source_content_tags_wrap_adversarial_text(self):
        """<source_content> tags must wrap even adversarial text."""
        prompt = build_analyst_prompt(INJECTION_ATTEMPT_SOURCE)
        user_content = prompt.messages[0]["content"]

        tag_start = user_content.find("<source_content>")
        tag_end = user_content.find("</source_content>")

        assert tag_start >= 0, "Missing <source_content> opening tag"
        assert tag_end > tag_start, "Missing </source_content> closing tag"

        # The adversarial text must be INSIDE the tags
        content_between_tags = user_content[tag_start:tag_end]
        assert "ignore previous instructions" in content_between_tags
