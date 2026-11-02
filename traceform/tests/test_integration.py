"""
# Integration tests — end-to-end pipeline with mocked Anthropic client and Celery eager mode.
#
# Phase 2 changes:
#   POST /api/v1/generations now returns 202 with {id, status: "queued"}.
#   Celery tasks run synchronously in tests via task_always_eager=True (set in conftest).
#   The test pattern is: enqueue → assert 202 → GET {id} until status=completed.
#   In eager mode, status is already "completed" by the time the POST returns.
#
# Use REAL_API=1 env var to hit the actual Anthropic API.
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.fixtures.knowledge_extraction import (
    APPLE_REVENUE_EXTRACTION,
    APPLE_REVENUE_SOURCE_TEXT,
)

REAL_API = os.getenv("REAL_API", "0") == "1"

# Mock analyst response returning APPLE_REVENUE_EXTRACTION as JSON
_MOCK_ANALYST_RESPONSE_DATA = {
    "summary": APPLE_REVENUE_EXTRACTION.summary,
    "entities": APPLE_REVENUE_EXTRACTION.entities.model_dump(),
    "facts": [f.model_dump() for f in APPLE_REVENUE_EXTRACTION.facts],
    "relationships": [r.model_dump() for r in APPLE_REVENUE_EXTRACTION.relationships],
    "domain": APPLE_REVENUE_EXTRACTION.domain,
    "source_tone": APPLE_REVENUE_EXTRACTION.source_tone,
    "sensitivity": APPLE_REVENUE_EXTRACTION.sensitivity.value,
    "sensitivity_source": "classifier",
    "sensitivity_confidence": 0.5,
}

_MOCK_GENERATOR_RESPONSE_DATA = {
    "content": "Great results from Apple! Revenue hit $85.8B in Q3 2024. #Tech #Apple",
    "facts_used": [f.model_dump() for f in APPLE_REVENUE_EXTRACTION.facts[:1]],
}


def _make_mock_anthropic_client():
    """Mock AsyncAnthropic that returns pre-canned responses."""
    def _build_response(content_dict):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(content_dict))]
        mock_response.usage.input_tokens = 800
        mock_response.usage.output_tokens = 250
        return mock_response

    call_count = {"n": 0}

    async def mock_create(**kwargs):
        call_count["n"] += 1
        # First call = Analyst Agent; subsequent calls = generators
        if call_count["n"] == 1:
            return _build_response(_MOCK_ANALYST_RESPONSE_DATA)
        return _build_response(_MOCK_GENERATOR_RESPONSE_DATA)

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=mock_create)
    return mock_client


@pytest.mark.skipif(REAL_API, reason="Skipped in mocked mode — set REAL_API=1 for real API test")
class TestFullPipelineMocked:

    async def test_healthz(self, client):
        response = await client.get("/api/v1/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_ingest_plain_text(self, client):
        response = await client.post(
            "/api/v1/sources/",
            data={"text": APPLE_REVENUE_SOURCE_TEXT},
        )
        assert response.status_code == 201
        body = response.json()
        assert "id" in body
        assert body["extracted_text_length"] == len(APPLE_REVENUE_SOURCE_TEXT)

    async def test_ingest_with_operator_sensitivity(self, client):
        response = await client.post(
            "/api/v1/sources/",
            data={"text": "Some internal report.", "sensitivity": "confidential"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["sensitivity"] == "confidential"
        assert body["sensitivity_source"] == "operator"

    async def test_ingest_invalid_sensitivity_rejected(self, client):
        response = await client.post(
            "/api/v1/sources/",
            data={"text": "Some text.", "sensitivity": "ultra-secret"},
        )
        assert response.status_code == 422

    async def test_ingest_no_input_rejected(self, client):
        response = await client.post("/api/v1/sources/")
        assert response.status_code == 422

    async def test_generation_returns_202_queued(self, client):
        """
        Phase 2 — POST /api/v1/generations must return 202 with status=queued.
        The Celery pipeline is mocked at the enqueue_generation call so we don't need
        a real broker or event loop for this test.
        """
        ingest_response = await client.post(
            "/api/v1/sources/",
            data={"text": APPLE_REVENUE_SOURCE_TEXT},
        )
        assert ingest_response.status_code == 201
        source_id = ingest_response.json()["id"]

        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            gen_response = await client.post(
                "/api/v1/generations/",
                json={
                    "source_id": source_id,
                    "output_types": ["linkedin_post"],
                    "params": {"audience": "tech professionals", "tone": "professional"},
                },
            )

        assert gen_response.status_code == 202
        body = gen_response.json()
        assert "id" in body
        assert body["status"] == "queued"
        assert body["prompt_version"] is not None
        assert "linkedin_post@" in body["prompt_version"]

    async def test_generation_full_pipeline_poll(self, client):
        """
        End-to-end contract test: POST returns 202 → GET returns the generation.
        The pipeline is mocked (enqueue_generation returns immediately).
        """
        # 1. Ingest
        ingest_response = await client.post(
            "/api/v1/sources/",
            data={"text": APPLE_REVENUE_SOURCE_TEXT},
        )
        assert ingest_response.status_code == 201
        source_id = ingest_response.json()["id"]

        # 2. Enqueue (mocked Celery)
        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            gen_response = await client.post(
                "/api/v1/generations/",
                json={
                    "source_id": source_id,
                    "output_types": ["linkedin_post"],
                },
            )

        assert gen_response.status_code == 202
        gen_id = gen_response.json()["id"]

        # 3. Poll GET — generation exists with status=queued (pipeline not run in this test)
        poll_response = await client.get(f"/api/v1/generations/{gen_id}")
        assert poll_response.status_code == 200
        poll_body = poll_response.json()
        assert poll_body["id"] == gen_id
        assert poll_body["status"] in ("queued", "running", "completed", "partial_failure")
        assert "artifacts" in poll_body

    async def test_generation_source_not_found(self, client):
        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            response = await client.post(
                "/api/v1/generations/",
                json={
                    "source_id": "00000000-0000-0000-0000-000000000000",
                    "output_types": ["linkedin_post"],
                },
            )
        assert response.status_code == 404

    async def test_generation_invalid_output_type(self, client):
        # Ingest first
        ingest_response = await client.post(
            "/api/v1/sources/",
            data={"text": "Test content."},
        )
        source_id = ingest_response.json()["id"]

        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            response = await client.post(
                "/api/v1/generations/",
                json={
                    "source_id": source_id,
                    "output_types": ["nonexistent_type_xyz"],
                },
            )
        assert response.status_code == 422

    async def test_fact_char_offsets_valid(self, client):
        """
        §3.7 — Every fact's [start_char:end_char] slice of extracted_text must be non-empty.
        This tests the traceability mechanism the whole product is built on (§1.3).
        """
        for fact in APPLE_REVENUE_EXTRACTION.facts:
            span = APPLE_REVENUE_SOURCE_TEXT[fact.start_char:fact.end_char]
            assert span, (
                f"Fact '{fact.claim[:50]}' has empty source span at "
                f"[{fact.start_char}:{fact.end_char}]. "
                "Char offsets must point to non-empty text in extracted_text."
            )

    async def test_get_generation_by_id(self, client):
        """GET /generations/{id} should return the generation."""
        ingest_response = await client.post(
            "/api/v1/sources/",
            data={"text": APPLE_REVENUE_SOURCE_TEXT},
        )
        source_id = ingest_response.json()["id"]

        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            gen_response = await client.post(
                "/api/v1/generations/",
                json={"source_id": source_id, "output_types": ["linkedin_post"]},
            )
        gen_id = gen_response.json()["id"]

        get_response = await client.get(f"/api/v1/generations/{gen_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == gen_id

    async def test_get_artifact_directly(self, client):
        """GET /generations/{id}/artifacts/{type} 404s when pipeline hasn't run yet."""
        ingest_response = await client.post(
            "/api/v1/sources/",
            data={"text": APPLE_REVENUE_SOURCE_TEXT},
        )
        source_id = ingest_response.json()["id"]

        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            gen_response = await client.post(
                "/api/v1/generations/",
                json={"source_id": source_id, "output_types": ["executive_summary"]},
            )
        gen_id = gen_response.json()["id"]

        # Artifact doesn't exist yet (pipeline mocked) — should 404
        artifact_response = await client.get(f"/api/v1/generations/{gen_id}/artifacts/executive_summary")
        assert artifact_response.status_code == 404

    async def test_prompt_version_pinned_at_enqueue(self, client):
        """
        §3.5 — prompt_version must be pinned on the Generation record at enqueue time
        (not mutable after the fact). The 202 response carries the pinned version.
        """
        ingest_response = await client.post(
            "/api/v1/sources/",
            data={"text": APPLE_REVENUE_SOURCE_TEXT},
        )
        source_id = ingest_response.json()["id"]

        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            gen_response = await client.post(
                "/api/v1/generations/",
                json={"source_id": source_id, "output_types": ["linkedin_post", "executive_summary"]},
            )
        body = gen_response.json()
        prompt_version = body["prompt_version"]

        # Both output types appear in the pinned version string
        assert "linkedin_post@" in prompt_version
        assert "executive_summary@" in prompt_version

    async def test_api_key_required(self, db_session):
        """§7 — Requests without API key should be rejected when keys are configured."""
        from httpx import ASGITransport, AsyncClient
        from api.main import app
        from api.dependencies import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        # Temporarily set API keys to force auth
        import api.dependencies as deps
        original_keys = deps._API_KEYS.copy()
        deps._API_KEYS = {"valid-key"}

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            response = await c.post("/api/v1/sources/", data={"text": "test"})

        deps._API_KEYS = original_keys
        app.dependency_overrides.clear()

        assert response.status_code == 401
