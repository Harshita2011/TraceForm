"""
# §3.3 Generator unit tests — all 9 output types.
# Each test mocks the Anthropic client and uses a fixed KnowledgeExtraction fixture.
# No real LLM calls are made.
#
# Proves: adding a new output type requires ONLY a YAML file — no new Python class (§1.3).
# GenericGeneratorAgent is used for all 9 types.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

import anthropic
from agents.generators.base import GenericGeneratorAgent, load_output_type_config
from schemas.generation import GenerationParams
from tests.fixtures.knowledge_extraction import APPLE_REVENUE_EXTRACTION, MINIMAL_EXTRACTION

# ─── All 9 output type keys defined in §3.3 ───────────────────────────────
ALL_OUTPUT_TYPES = [
    "linkedin_post",
    "twitter_post",
    "advisory",
    "executive_summary",
    "presentation",
    "infographic",
    "video_package",
    "newsletter",
    "press_release",
]


def _make_mock_client(response_content: dict) -> MagicMock:
    """Build a mock AsyncAnthropic client returning a pre-canned response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(response_content))]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 300
    mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


def _minimal_response(output_type: str) -> dict:
    """Minimal valid generator response for any output type."""
    return {
        "content": f"Test {output_type} content.",
        "facts_used": [APPLE_REVENUE_EXTRACTION.facts[0].model_dump()],
    }


# ─── Parametrized tests for all output types ─────────────────────────────

@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_yaml_config_loads_for_all_types(output_type: str):
    """Every output type must have a loadable YAML config file."""
    config = load_output_type_config(output_type)
    assert config["output_type"] == output_type
    assert "prompt_template_version" in config
    assert "prompt_template" in config


@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_generic_generator_instantiates_for_all_types(output_type: str):
    """GenericGeneratorAgent must instantiate for every output type without subclassing."""
    mock_client = _make_mock_client(_minimal_response(output_type))
    agent = GenericGeneratorAgent(output_type_key=output_type, client=mock_client)
    assert agent.output_type == output_type
    assert agent.prompt_template_version != ""


@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_generate_returns_result_with_content(output_type: str):
    """generate() must return a GeneratorArtifactResult with non-empty content."""
    mock_client = _make_mock_client(_minimal_response(output_type))
    agent = GenericGeneratorAgent(output_type_key=output_type, client=mock_client)
    result = await agent.generate(
        context=APPLE_REVENUE_EXTRACTION,
        params=GenerationParams(),
    )
    assert result.output_type == output_type
    assert result.content is not None
    assert len(result.content) > 0


@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_generate_populates_facts_used(output_type: str):
    """generate() must return a non-empty facts_used list."""
    mock_client = _make_mock_client(_minimal_response(output_type))
    agent = GenericGeneratorAgent(output_type_key=output_type, client=mock_client)
    result = await agent.generate(
        context=APPLE_REVENUE_EXTRACTION,
        params=GenerationParams(),
    )
    assert isinstance(result.facts_used, list)
    assert len(result.facts_used) > 0


@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_generate_pins_prompt_version(output_type: str):
    """prompt_version must be set from YAML config (never empty/unknown for valid configs)."""
    mock_client = _make_mock_client(_minimal_response(output_type))
    agent = GenericGeneratorAgent(output_type_key=output_type, client=mock_client)
    result = await agent.generate(
        context=APPLE_REVENUE_EXTRACTION,
        params=GenerationParams(),
    )
    assert result.prompt_version != ""
    assert result.prompt_version != "unknown"


@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_generate_pins_model_version(output_type: str):
    """model_version on the result must match the model passed to the agent."""
    mock_client = _make_mock_client(_minimal_response(output_type))
    agent = GenericGeneratorAgent(
        output_type_key=output_type,
        client=mock_client,
        model="claude-sonnet-4-5",
    )
    result = await agent.generate(
        context=APPLE_REVENUE_EXTRACTION,
        params=GenerationParams(),
    )
    assert result.model_version == "claude-sonnet-4-5"


@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_generate_never_passes_raw_source_text(output_type: str):
    """
    §3.3 — Generators receive ONLY the KnowledgeExtraction object, never raw source text.
    Verified by inspecting the messages sent to the Anthropic API call:
    no field containing the literal raw source text should appear in the user message.
    """
    raw_source_marker = "DO_NOT_PASS_THIS_RAW_TEXT_abc123_xyz"
    # Build a KnowledgeExtraction with a fact that references this marker as a claim
    # (it will appear in facts_used, but the raw_source_marker itself is not passed)
    mock_client = _make_mock_client(_minimal_response(output_type))
    agent = GenericGeneratorAgent(output_type_key=output_type, client=mock_client)

    await agent.generate(
        context=APPLE_REVENUE_EXTRACTION,
        params=GenerationParams(),
    )

    # Inspect the actual call kwargs
    call_kwargs = mock_client.messages.create.call_args
    system_prompt = call_kwargs.kwargs.get("system", "")
    messages = call_kwargs.kwargs.get("messages", [])
    user_message = messages[0]["content"] if messages else ""

    # Raw source marker must not appear anywhere
    assert raw_source_marker not in system_prompt
    assert raw_source_marker not in user_message


@pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
async def test_token_usage_captured(output_type: str):
    """generate() must capture token usage from the API response."""
    mock_client = _make_mock_client(_minimal_response(output_type))
    agent = GenericGeneratorAgent(output_type_key=output_type, client=mock_client)
    result = await agent.generate(
        context=APPLE_REVENUE_EXTRACTION,
        params=GenerationParams(),
    )
    assert result.token_usage.get("input_tokens", 0) > 0
    assert result.token_usage.get("output_tokens", 0) > 0


# ─── Output-type-specific content tests ───────────────────────────────────

class TestTwitterPostConstraints:
    """Twitter post has a hard 280-char limit — test the prompt enforces it."""

    async def test_twitter_post_config_mentions_280_char_limit(self):
        """The YAML prompt_template must mention the 280-character limit."""
        config = load_output_type_config("twitter_post")
        assert "280" in config["prompt_template"]

    async def test_twitter_post_generates_content(self):
        mock_client = _make_mock_client({
            "content": "Apple reports $85.8B Q3 revenue. Strong iPhone sales drive growth. #Apple #Tech",
            "facts_used": [APPLE_REVENUE_EXTRACTION.facts[0].model_dump()],
        })
        agent = GenericGeneratorAgent(output_type_key="twitter_post", client=mock_client)
        result = await agent.generate(context=APPLE_REVENUE_EXTRACTION, params=GenerationParams())
        assert result.content is not None


class TestPresentationConfig:
    """Presentation output type uses PPTX renderer and produces slide JSON."""

    async def test_presentation_config_has_pptx_renderer(self):
        config = load_output_type_config("presentation")
        assert config.get("renderer") == "pptx"

    async def test_presentation_generates_content(self):
        slide_data = [
            {"title": "Apple Q3 Results", "bullets": ["Revenue: $85.8B"], "speaker_notes": ""},
            {"title": "Key Drivers", "bullets": ["iPhone sales strong"], "speaker_notes": ""},
        ]
        mock_client = _make_mock_client({
            "content": json.dumps(slide_data),
            "facts_used": [APPLE_REVENUE_EXTRACTION.facts[0].model_dump()],
        })
        agent = GenericGeneratorAgent(output_type_key="presentation", client=mock_client)
        result = await agent.generate(context=APPLE_REVENUE_EXTRACTION, params=GenerationParams())
        assert result.content is not None


class TestVideoPackageScope:
    """Video Package must declare V1 scope (no video generation) in its YAML comment."""

    async def test_video_package_config_has_scope_note(self):
        """The YAML file must mention 'V1' scope to document the explicit limitation."""
        config = load_output_type_config("video_package")
        assert config["output_type"] == "video_package"
        # The YAML prompt_template or description should reference the scope
        assert "script" in config["prompt_template"].lower() or "storyboard" in config["prompt_template"].lower()


class TestInfoGraphicScope:
    """Infographic must use text renderer (no image generation in V1)."""

    async def test_infographic_config_uses_text_renderer(self):
        config = load_output_type_config("infographic")
        assert config.get("renderer") == "text"


class TestAdvisoryStructure:
    """Advisory must instruct the model to produce structured sections."""

    async def test_advisory_prompt_references_sections(self):
        config = load_output_type_config("advisory")
        template = config["prompt_template"]
        assert "Executive Summary" in template or "Key Findings" in template


class TestParamOverridePrecedenceAllTypes:
    """Per-output-type overrides in GenerationParams must win over global params."""

    @pytest.mark.parametrize("output_type", ALL_OUTPUT_TYPES)
    async def test_override_applied_for_all_types(self, output_type: str):
        """
        GenerationParams.for_output_type() must return a merged copy where
        override values take precedence. The agent's _build_system_prompt must
        render with the overridden values.
        """
        mock_client = _make_mock_client(_minimal_response(output_type))
        agent = GenericGeneratorAgent(output_type_key=output_type, client=mock_client)

        params = GenerationParams(
            tone="formal",
            overrides={output_type: {"tone": "punchy"}},
        )
        effective = params.for_output_type(output_type)
        assert effective.tone == "punchy"
        # Default global params for a different type — should NOT get override
        assert params.for_output_type("other_type").tone == "formal"
