"""Regression checks for source grounding and generation failure handling."""
import json
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from agents.generators.base import GenericGeneratorAgent
from agents.generators.section_validator import heal_artifact_sections
from agents.generators.blueprints import get_blueprint
from agents.llm import call_llm
from schemas.generation import GenerationParams
from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION


def test_missing_sections_do_not_invent_business_facts():
    content = heal_artifact_sections("Source-backed draft.", get_blueprint("press_release"), MINIMAL_EXTRACTION)
    assert "source does not provide enough information" in content
    assert "press@enterprise.com" not in content
    assert "stated executive leadership" not in content
    assert "21-day" not in content


def test_prompt_includes_user_requirements():
    generator = GenericGeneratorAgent("research_report")
    prompt = generator._build_system_prompt(GenerationParams(
        language="es", detail_level="high", objective="Explain water leaks", style="Plain language"
    ))
    for expected in ("Language: es", "Detail level: high", "Explain water leaks", "Plain language"):
        assert expected in prompt


@pytest.mark.parametrize("payload", [[], {"content": ""}, {"content": None}, {"content": "Text", "facts_used": "wrong"}])
def test_malformed_generator_payload_rejected(payload):
    with pytest.raises(ValueError):
        GenericGeneratorAgent("research_report")._parse_response(json.dumps(payload))


async def test_provider_failure_does_not_fabricate_success(monkeypatch):
    monkeypatch.delenv("TRACEFORM_ALLOW_SYNTHETIC_LLM", raising=False)
    with pytest.raises(RuntimeError, match="LLM generation unavailable"):
        await call_llm(None, "test-model", "Review the source", "source", json_mode=True)


async def test_retired_gemini_model_uses_configured_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "available-model, available-model")
    attempted = []

    def generate_content(*, model, **kwargs):
        attempted.append(model)
        if model == "retired-model":
            raise RuntimeError("404 model no longer available")
        return SimpleNamespace(text="Source-backed output", usage_metadata=None)

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    text, _ = await call_llm(client, "retired-model", "Summarize", "Source text")
    assert text == "Source-backed output"
    assert attempted == ["retired-model", "available-model"]


async def test_gemini_default_does_not_retry_retired_models(monkeypatch):
    from agents.llm import get_default_model
    for name in ("GEMINI_MODEL", "ANTHROPIC_MODEL", "GEMINI_FALLBACK_MODELS", "TRACEFORM_ALLOW_SYNTHETIC_LLM"):
        monkeypatch.delenv(name, raising=False)
    attempted = []

    def generate_content(*, model, **kwargs):
        attempted.append(model)
        raise RuntimeError("Provider unavailable")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    with pytest.raises(RuntimeError, match="LLM generation unavailable"):
        await call_llm(client, get_default_model(), "Summarize", "Source text")
    assert attempted == ["gemini-3.1-flash-lite"]


async def test_background_exception_marks_generation_failed(session_factory):
    from db.models import Source, Generation
    from schemas.enums import SensitivityLevel, SensitivitySource, GenerationStatus
    from orchestrator.jobs import _run_background_generation
    async with session_factory() as db:
        source = Source(extracted_text="Evidence", sensitivity=SensitivityLevel.PUBLIC,
                        sensitivity_source=SensitivitySource.OPERATOR, sensitivity_confidence=1.0)
        db.add(source)
        await db.flush()
        generation = Generation(source_id=source.id, output_types=["research_report"],
                                params={}, status=GenerationStatus.RUNNING)
        db.add(generation)
        await db.commit()
        generation_id = generation.id
    with patch("orchestrator.jobs.AsyncSessionLocal", session_factory), patch(
        "orchestrator.jobs._async_run_generation_pipeline", side_effect=RuntimeError("review failed")
    ):
        await _run_background_generation(str(generation_id))
    async with session_factory() as db:
        assert (await db.get(Generation, generation_id)).status == GenerationStatus.FAILED


def test_guidance_does_not_inject_retention_plan():
    from agents.generators.insight_engine import InsightEngine
    from agents.generators.recommendation_engine import RecommendationEngine
    insights = InsightEngine().extract_insights(MINIMAL_EXTRACTION)
    recommendations = RecommendationEngine().generate_recommendations(MINIMAL_EXTRACTION, insights)
    assert "400 bps" not in recommendations.to_guidance_prompt()
    assert "retention stabilization" not in recommendations.to_guidance_prompt()
    assert all(item.raw_fact in [f.claim for f in MINIMAL_EXTRACTION.facts] for item in insights.all_insights())


def test_duplicate_formats_and_invalid_budgets_rejected():
    from uuid import uuid4
    from pydantic import ValidationError
    from schemas.generation import GenerationRequest
    base = {"source_id": uuid4(), "output_types": ["research_report"]}
    for changes in ({"output_types": ["research_report", "research_report"]},
                    {"budget_type": "unknown"}, {"budget_ceiling": -1}):
        with pytest.raises(ValidationError):
            GenerationRequest(**{**base, **changes})


def test_truncated_json_is_not_published_as_markdown():
    with pytest.raises(ValueError, match="malformed or truncated JSON"):
        GenericGeneratorAgent("executive_summary")._parse_response('{"content": "unfinished')
