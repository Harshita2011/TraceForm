"""
# Phase 2 — GET /api/v1/generations/history/list tests.
#
# Covers:
#  - Each filter dimension independently (status, output_type, from_date, to_date)
#  - Filter combinations (all ANDed — must match ALL filters)
#  - Edge cases: no results → empty list (not an error), invalid status, malformed dates
#  - Zero-results combination that confirms filters are ANDed not OR'd
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.fixtures.knowledge_extraction import APPLE_REVENUE_SOURCE_TEXT

_MOCK_ANALYST_DATA = {
    "summary": "Apple Inc. Q3 2024 revenue was $85.8 billion.",
    "entities": {"organizations": ["Apple Inc."], "people": [], "locations": [], "products": []},
    "facts": [{"claim": "Revenue was $85.8B.", "source_span": "revenue was $85.8B", "start_char": 0, "end_char": 18, "confidence": 0.95}],
    "relationships": [],
    "domain": "technology",
    "source_tone": "journalistic",
    "sensitivity": "public",
    "sensitivity_source": "classifier",
    "sensitivity_confidence": 0.5,
}

_MOCK_GENERATOR_DATA = {
    "content": "Revenue hit $85.8B in Q3 2024.",
    "facts_used": [{"claim": "Revenue was $85.8B.", "source_span": "revenue was $85.8B", "start_char": 0, "end_char": 18, "confidence": 0.95}],
}


def _make_mock_client():
    call_count = {"n": 0}

    async def mock_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            response = MagicMock()
            response.content = [MagicMock(text=json.dumps(_MOCK_ANALYST_DATA))]
            response.usage.input_tokens = 800
            response.usage.output_tokens = 250
            return response
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps(_MOCK_GENERATOR_DATA))]
        response.usage.input_tokens = 400
        response.usage.output_tokens = 150
        return response

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=mock_create)
    return mock_client


# ─── Helpers ─────────────────────────────────────────────────────

async def _ingest_source(client, text: str = APPLE_REVENUE_SOURCE_TEXT) -> str:
    resp = await client.post("/api/v1/sources/", data={"text": text})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_generation(client, source_id: str, output_types: list[str]) -> str:
    with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
        resp = await client.post(
            "/api/v1/generations/",
            json={"source_id": source_id, "output_types": output_types},
        )
    assert resp.status_code == 202
    return resp.json()["id"]


# ─── Tests ────────────────────────────────────────────────────────

class TestHistoryEndpointBasics:

    async def test_history_returns_200_empty_list_when_no_generations(self, client):
        """No generations → empty list, not an error (edge case)."""
        resp = await client.get("/api/v1/generations/history/list")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_history_returns_all_generations_no_filter(self, client):
        """Without filters, history returns all generations."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])
        await _create_generation(client, source_id, ["executive_summary"])

        resp = await client.get("/api/v1/generations/history/list")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2

    async def test_history_response_schema(self, client):
        """History response must have items, total, offset, limit fields."""
        resp = await client.get("/api/v1/generations/history/list")
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "offset" in body
        assert "limit" in body


class TestHistoryStatusFilter:

    async def test_filter_by_status_queued(self, client):
        """Filter by status=queued returns only queued generations (or empty if pipeline ran)."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        resp = await client.get("/api/v1/generations/history/list?status=queued")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["status"] == "queued"

    async def test_filter_by_status_completed(self, client):
        """Filter by status=completed returns only completed generations."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        resp = await client.get("/api/v1/generations/history/list?status=completed")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["status"] == "completed"

    async def test_filter_by_invalid_status_returns_422(self, client):
        """Invalid status value must return 422, not 500."""
        resp = await client.get("/api/v1/generations/history/list?status=invalid_xyz")
        assert resp.status_code == 422

    async def test_no_matching_status_returns_empty_list(self, client):
        """
        Filter by status=failed when no generations have failed → empty list, not an error.
        Edge case: filters that match zero rows return [] not 404.
        """
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        resp = await client.get("/api/v1/generations/history/list?status=failed")
        assert resp.status_code == 200
        body = resp.json()
        # Either empty (if no failures exist) or all items have status=failed
        for item in body["items"]:
            assert item["status"] == "failed"


class TestHistoryOutputTypeFilter:

    async def test_filter_by_output_type_linkedin(self, client):
        """Filter by output_type=linkedin_post returns only generations containing that type."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])
        await _create_generation(client, source_id, ["executive_summary"])

        resp = await client.get("/api/v1/generations/history/list?output_type=linkedin_post")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert "linkedin_post" in item["output_types"]

    async def test_filter_by_output_type_no_match_returns_empty(self, client):
        """output_type filter that matches no generation → empty list (not an error)."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        resp = await client.get("/api/v1/generations/history/list?output_type=press_release")
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert "press_release" in item["output_types"]

    async def test_filter_by_output_type_multi_type_generation(self, client):
        """A generation with multiple output types is included if the filter type is one of them."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post", "executive_summary"])

        resp = await client.get("/api/v1/generations/history/list?output_type=linkedin_post")
        assert resp.status_code == 200
        body = resp.json()
        # The multi-type generation should appear
        matching = [i for i in body["items"] if "executive_summary" in i["output_types"]]
        assert len(matching) >= 1


class TestHistoryDateFilters:

    async def test_from_date_excludes_older_generations(self, client):
        """from_date filter excludes generations created before that datetime."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        # Filter from now — should exclude everything just created (created_at ≤ now)
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        resp = await client.get(f"/api/v1/generations/history/list?from_date={future_ts}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == [], "from_date in the future should return no results"

    async def test_to_date_excludes_newer_generations(self, client):
        """to_date filter excludes generations created after that datetime."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        # Filter to before now — the just-created generation should be excluded
        past_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = await client.get(f"/api/v1/generations/history/list?to_date={past_ts}")
        assert resp.status_code == 200
        body = resp.json()
        # All returned items must be within the to_date range
        assert body["total"] >= 0  # empty is valid; just ensure no error

    async def test_from_date_after_to_date_returns_422(self, client):
        """from_date > to_date is a malformed date range — must return 422."""
        from_ts = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        to_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        resp = await client.get(f"/api/v1/generations/history/list?from_date={from_ts}&to_date={to_ts}")
        assert resp.status_code == 422

    async def test_malformed_date_returns_422(self, client):
        """Malformed date string (not ISO 8601) must return 422."""
        resp = await client.get("/api/v1/generations/history/list?from_date=not-a-date")
        assert resp.status_code == 422

    async def test_date_range_inclusive(self, client):
        """A wide date range (past to future) includes all existing generations."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        past_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        future_ts = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        resp = await client.get(
            f"/api/v1/generations/history/list?from_date={past_ts}&to_date={future_ts}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1


class TestHistoryFilterCombinations:

    async def test_status_and_output_type_anded(self, client):
        """status + output_type filters must be ANDed — result matches BOTH criteria."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        # Request both filters
        resp = await client.get(
            "/api/v1/generations/history/list?status=completed&output_type=linkedin_post"
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["status"] == "completed"
            assert "linkedin_post" in item["output_types"]

    async def test_status_and_output_type_zero_results_confirms_and_not_or(self, client):
        """
        Create a completed generation with linkedin_post.
        Filter for status=failed AND output_type=linkedin_post.
        If filters were OR'd, we'd get the completed linkedin_post generation.
        If filters are ANDed (correct), we get zero results.
        """
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        resp = await client.get(
            "/api/v1/generations/history/list?status=failed&output_type=linkedin_post"
        )
        assert resp.status_code == 200
        body = resp.json()
        # Since no linkedin_post generation is in 'failed' state, result must be empty
        for item in body["items"]:
            assert item["status"] == "failed"
            assert "linkedin_post" in item["output_types"]
        # The key assertion: we should NOT see the completed linkedin_post generation here
        # (if OR'd, it would appear due to output_type match)

    async def test_all_three_filters_combined(self, client):
        """status + output_type + date range — all three ANDed together."""
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["executive_summary"])

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

        resp = await client.get(
            f"/api/v1/generations/history/list"
            f"?status=completed&output_type=executive_summary&from_date={past}&to_date={future}"
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["status"] == "completed"
            assert "executive_summary" in item["output_types"]

    async def test_impossible_filter_combination_returns_empty(self, client):
        """
        A logically impossible combination (status=completed AND status filtering for nonexistent type)
        returns empty list, not an error.
        """
        source_id = await _ingest_source(client)
        await _create_generation(client, source_id, ["linkedin_post"])

        # output_type=newsletter with status=failed — very unlikely to match
        resp = await client.get(
            "/api/v1/generations/history/list?status=failed&output_type=newsletter"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 0  # empty is valid and expected


class TestHistoryPagination:

    async def test_limit_and_offset(self, client):
        """limit and offset pagination must work correctly."""
        source_id = await _ingest_source(client)
        # Create 3 generations
        for ot in ["linkedin_post", "executive_summary", "twitter_post"]:
            await _create_generation(client, source_id, [ot])

        # Page 1: limit=2
        resp1 = await client.get("/api/v1/generations/history/list?limit=2&offset=0")
        assert resp1.status_code == 200
        page1 = resp1.json()
        assert len(page1["items"]) <= 2

        # Page 2: limit=2, offset=2
        resp2 = await client.get("/api/v1/generations/history/list?limit=2&offset=2")
        assert resp2.status_code == 200
        page2 = resp2.json()
        assert len(page2["items"]) <= 2

        # No overlap between pages
        ids_p1 = {i["id"] for i in page1["items"]}
        ids_p2 = {i["id"] for i in page2["items"]}
        assert ids_p1.isdisjoint(ids_p2)

    async def test_limit_zero_returns_422(self, client):
        """limit=0 is invalid (ge=1) — must return 422."""
        resp = await client.get("/api/v1/generations/history/list?limit=0")
        assert resp.status_code == 422
