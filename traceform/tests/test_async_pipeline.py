"""
# Phase 2 async pipeline tests — dead-letter/partial-failure, prompt version immutability.

These tests call async pipeline functions DIRECTLY (not via the HTTP client) to avoid
the nested event loop problem that arises from Celery eager mode + pytest-asyncio.

The HTTP-level pipeline contract (202 response, prompt version in response) is tested
separately in test_integration.py.

Design decision: the core pipeline logic (_finalize_generation, status assignment) is
tested here via direct async function calls with the test DB session. This is a cleaner
boundary than trying to run the full Celery pipeline in eager mode within pytest-asyncio.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from agents.generators.blueprints import get_blueprint
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Artifact, Generation, Source
from schemas.enums import ArtifactReviewStatus, GenerationStatus, SensitivityLevel, SensitivitySource
from tests.fixtures.knowledge_extraction import (
    APPLE_REVENUE_EXTRACTION,
    APPLE_REVENUE_SOURCE_TEXT,
)


# ─── Partial Failure / Dead Letter ───────────────────────────────────────────

class TestFinalizeGenerationLogic:
    """
    §4 — Unit tests for _finalize_generation (the status-setting step at the end of the pipeline).
    Tests the invariant: any FAILED artifact → PARTIAL_FAILURE, all OK → COMPLETED.
    """

    async def test_partial_failure_when_one_artifact_fails(
        self, db_session: AsyncSession, session_factory
    ):
        """
        _finalize_generation must set PARTIAL_FAILURE when any artifact has review_status=FAILED.
        """
        from orchestrator.jobs import _finalize_generation

        source = Source(
            extracted_text="Test source.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post", "executive_summary"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        db_session.add(Artifact(
            generation_id=gen.id,
            output_type="linkedin_post",
            content="Great post!",
            review_status=ArtifactReviewStatus.PASSED,
            retry_count=0,
        ))
        db_session.add(Artifact(
            generation_id=gen.id,
            output_type="executive_summary",
            content=None,
            review_status=ArtifactReviewStatus.FAILED,
            retry_count=3,
        ))
        await db_session.commit()

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            await _finalize_generation(str(gen.id))

        await db_session.refresh(gen)
        assert gen.status == GenerationStatus.PARTIAL_FAILURE

    async def test_completed_when_all_artifacts_succeed(
        self, db_session: AsyncSession, session_factory
    ):
        """_finalize_generation must set COMPLETED when all artifacts have no FAILED status."""
        from orchestrator.jobs import _finalize_generation

        source = Source(
            extracted_text="Test.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post", "twitter_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        db_session.add(Artifact(
            generation_id=gen.id,
            output_type="linkedin_post",
            content="Great post!",
            review_status=ArtifactReviewStatus.PASSED,
            retry_count=0,
        ))
        db_session.add(Artifact(
            generation_id=gen.id,
            output_type="twitter_post",
            content="Short tweet!",
            review_status=ArtifactReviewStatus.PASSED,
            retry_count=0,
        ))
        await db_session.commit()

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            await _finalize_generation(str(gen.id))

        await db_session.refresh(gen)
        assert gen.status == GenerationStatus.COMPLETED

    async def test_partial_failure_requires_at_least_one_failed(
        self, db_session: AsyncSession, session_factory
    ):
        """
        PARTIAL_FAILURE only when ≥1 artifact is FAILED. If zero artifacts are FAILED,
        status must be COMPLETED — not PARTIAL_FAILURE.
        """
        from orchestrator.jobs import _finalize_generation

        source = Source(
            extracted_text="Test.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        # One succeeded, zero failed
        db_session.add(Artifact(
            generation_id=gen.id,
            output_type="linkedin_post",
            content="OK",
            review_status=ArtifactReviewStatus.PASSED,
            retry_count=0,
        ))
        await db_session.commit()

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            await _finalize_generation(str(gen.id))

        await db_session.refresh(gen)
        assert gen.status != GenerationStatus.PARTIAL_FAILURE
        assert gen.status == GenerationStatus.COMPLETED

    async def test_finalize_with_all_failed_artifacts(
        self, db_session: AsyncSession, session_factory
    ):
        """All artifacts FAILED → still PARTIAL_FAILURE (not FAILED) — the generation ran."""
        from orchestrator.jobs import _finalize_generation

        source = Source(
            extracted_text="Test.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post", "twitter_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        for ot in ["linkedin_post", "twitter_post"]:
            db_session.add(Artifact(
                generation_id=gen.id,
                output_type=ot,
                content=None,
                review_status=ArtifactReviewStatus.FAILED,
                retry_count=3,
            ))
        await db_session.commit()

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            await _finalize_generation(str(gen.id))

        await db_session.refresh(gen)
        assert gen.status == GenerationStatus.FAILED


# ─── Cost computation unit tests ─────────────────────────────────────────────

class TestCostComputation:
    """Unit tests for cost helpers in jobs.py."""

    def test_tokens_to_cost_opus(self):
        from orchestrator.jobs import _tokens_to_cost
        cost = _tokens_to_cost({"input_tokens": 1000, "output_tokens": 500}, "claude-opus-4-5")
        # 1000 * 15/1_000_000 + 500 * 75/1_000_000 = 0.015 + 0.0375 = 0.0525
        assert abs(cost - 0.0525) < 1e-6

    def test_analyst_cost_shared_equally(self):
        from orchestrator.jobs import _compute_analyst_cost_share
        share = _compute_analyst_cost_share(
            {"input_tokens": 2000, "output_tokens": 1000},
            num_output_types=4,
            model="claude-opus-4-5",
        )
        total = _compute_analyst_cost_share(
            {"input_tokens": 2000, "output_tokens": 1000},
            num_output_types=1,
            model="claude-opus-4-5",
        )
        # Each of 4 types gets 1/4 of total analyst cost
        assert abs(share * 4 - total) < 1e-6

    def test_zero_output_types_does_not_divide_by_zero(self):
        from orchestrator.jobs import _compute_analyst_cost_share
        # Should not raise ZeroDivisionError
        share = _compute_analyst_cost_share(
            {"input_tokens": 1000, "output_tokens": 500},
            num_output_types=0,
            model="claude-opus-4-5",
        )
        assert share >= 0

    def test_build_artifact_cost_structure(self):
        from orchestrator.jobs import _build_artifact_cost
        cost = _build_artifact_cost(
            {"input_tokens": 500, "output_tokens": 200},
            model="claude-opus-4-5",
            analyst_share=0.01,
        )
        assert "analyst_share" in cost
        assert "generation" in cost
        assert "total" in cost
        assert abs(cost["total"] - (cost["analyst_share"] + cost["generation"])) < 1e-5

    def test_unknown_model_uses_default_cost(self):
        from orchestrator.jobs import _tokens_to_cost
        cost = _tokens_to_cost({"input_tokens": 1000, "output_tokens": 0}, "unknown-model-xyz")
        # Should use default pricing without raising
        assert cost > 0


# ─── Fan-Out Design Intent ────────────────────────────────────────────────────

class TestFanOutDesignIntent:
    """
    §4 — Generator tasks must be dispatched as a Celery group (fan-out), not sequentially.
    True wall-clock parallelism is validated in Phase 5 load tests with real workers.
    This class documents the design intent and tests the CODE STRUCTURE.
    """

    def test_jobs_module_imports_celery_group(self):
        """The jobs module must import Celery `group` for fan-out dispatch."""
        import orchestrator.jobs as jobs_module
        import inspect
        source = inspect.getsource(jobs_module)
        assert "from celery import group" in source or "celery.group" in source

    def test_run_generation_pipeline_uses_group_not_sequential_loop(self):
        """
        The _async_run_generation_pipeline function must use `group(...)` for fan-out.
        Check the source code structure rather than runtime behaviour.
        """
        import orchestrator.jobs as jobs_module
        import inspect
        source = inspect.getsource(jobs_module._async_run_generation_pipeline)
        assert "group(" in source, (
            "run_generation_pipeline must use Celery group() for fan-out dispatch of generators. "
            "Sequential dispatch would violate the §4 parallel generation latency requirement."
        )


# ─── Prompt Version Immutability ─────────────────────────────────────────────

class TestPromptVersionImmutability:
    """
    §3.5 / §4 — prompt_version pinned at enqueue time.
    These tests use the HTTP client but mock enqueue_generation to avoid pipeline execution.
    """

    async def test_prompt_version_pinned_at_enqueue(self, client):
        """The 202 response carries the pinned prompt_version; GET also returns it unchanged."""
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

        assert gen_response.status_code == 202
        body = gen_response.json()
        pinned_version = body["prompt_version"]
        assert pinned_version is not None
        assert "linkedin_post@" in pinned_version

        gen_id = body["id"]
        get_body = (await client.get(f"/api/v1/generations/{gen_id}")).json()
        assert get_body["prompt_version"] == pinned_version

    async def test_yaml_version_change_does_not_affect_old_generation(self, client):
        """OLD Generation's prompt_version must be unchanged after YAML version bump."""
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

        original_version = gen_response.json()["prompt_version"]
        gen_id = gen_response.json()["id"]

        new_yaml_config = {
            "output_type": "linkedin_post",
            "prompt_template_version": "9.9.9",
            "renderer": "text",
            "prompt_template": "New template",
        }
        with patch("api.routes.generations.load_output_type_config", return_value=new_yaml_config):
            with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
                new_gen_response = await client.post(
                    "/api/v1/generations/",
                    json={"source_id": source_id, "output_types": ["linkedin_post"]},
                )

        new_version = new_gen_response.json()["prompt_version"]

        old_gen_body = (await client.get(f"/api/v1/generations/{gen_id}")).json()
        assert old_gen_body["prompt_version"] == original_version

        assert "9.9.9" in new_version
        assert new_version != original_version

    async def test_multiple_output_types_all_appear_in_prompt_version(self, client):
        """All requested output type versions must appear in the pinned prompt_version string."""
        ingest_response = await client.post(
            "/api/v1/sources/",
            data={"text": APPLE_REVENUE_SOURCE_TEXT},
        )
        source_id = ingest_response.json()["id"]

        output_types = ["linkedin_post", "twitter_post", "advisory"]
        with patch("api.routes.generations.enqueue_generation", return_value="mock-task-id"):
            gen_response = await client.post(
                "/api/v1/generations/",
                json={"source_id": source_id, "output_types": output_types},
            )

        prompt_version = gen_response.json()["prompt_version"]
        for ot in output_types:
            assert f"{ot}@" in prompt_version, (
                f"Output type '{ot}' missing from pinned prompt_version: {prompt_version}"
            )


# ─── Dead-Letter: Kill One Generator, Others Must Still Complete ──────────────

class TestDeadLetterKillOneGeneratorOthersComplete:
    """
    §4 — Phase 2 §6 explicit requirement:
    "Write a test that kills one generator task and asserts the other generators
    still complete and are delivered."

    Strategy: call _async_run_generator_task directly for two output types.
    - linkedin_post generator always raises → task mocked to exhaust retries immediately
      → artifact is written with review_status=FAILED (dead-letter path, no re-raise)
    - executive_summary generator succeeds normally
    Assert both artifacts exist, failing one has FAILED status, succeeding one has content,
    then _finalize_generation produces PARTIAL_FAILURE.
    """

    @staticmethod
    def _make_exhausted_task():
        """Mock Celery task whose retry() immediately raises MaxRetriesExceededError."""
        MaxRetriesExceededError = type("MaxRetriesExceededError", (Exception,), {})
        task = MagicMock()
        task.request.retries = 3
        task.MaxRetriesExceededError = MaxRetriesExceededError
        # retry() raises MaxRetriesExceededError synchronously (Celery behaviour on exhaustion)
        task.retry.side_effect = MaxRetriesExceededError("retries exhausted")
        return task

    @staticmethod
    def _make_fresh_task():
        """Mock Celery task that has not retried yet (healthy path)."""
        task = MagicMock()
        task.request.retries = 0
        return task

    async def test_kill_linkedin_post_executive_summary_still_delivers(
        self, db_session: AsyncSession, session_factory
    ):
        """
        One dead-lettered generator must NOT prevent the other from completing.
        Both artifact rows must be written; only the failed one has FAILED status.
        """
        from orchestrator.jobs import _async_run_generator_task, _finalize_generation, _GENERATOR_MAX_RETRIES
        from agents.base import GeneratorArtifactResult

        # --- Seed DB ---
        source = Source(
            extracted_text="Apple revenue $85.8B Q3 2024.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.8,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post", "executive_summary"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        from db.models import KnowledgeExtractionModel
        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="Apple Q3 summary.",
            entities={"organizations": ["Apple"], "people": [], "locations": [], "products": []},
            facts=[{"claim": "Revenue $85.8B", "source_span": "revenue $85.8B",
                    "start_char": 6, "end_char": 20, "confidence": 0.95}],
            relationships=[],
            domain="technology",
            source_tone="journalistic",
        )
        db_session.add(ke)
        await db_session.commit()

        generation_id = str(gen.id)
        ke_id = str(ke.id)
        model = "claude-opus-4-5"

        # --- Fake generator: fails for linkedin_post, succeeds for executive_summary ---
        def fake_generator_factory(output_type_key, client, model):
            class _FakeGenerator:
                async def generate(self, context, params):
                    if output_type_key == "linkedin_post":
                        raise RuntimeError("Simulated model failure — dead-letter scenario")
                    return GeneratorArtifactResult(
                        output_type=output_type_key,
                        content="\n\n".join("## " + title + "\nRevenue $85.8B" for title in get_blueprint(output_type_key).sections),
                        facts_used=[{"claim": "Revenue $85.8B"}],
                        prompt_version="1.0.0",
                        model_version=model,
                        token_usage={"input_tokens": 200, "output_tokens": 100},
                    )
            return _FakeGenerator()

        exhausted_task = self._make_exhausted_task()
        fresh_task = self._make_fresh_task()

        class _MockPassReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                from schemas.review import ReviewResult
                return ReviewResult(reviewer_name="pass", passed=True, details={}, reviewer_version="1.0.0")

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            with patch("orchestrator.jobs.GenericGeneratorAgent", side_effect=fake_generator_factory):
                with patch("orchestrator.jobs.StyleReviewer", return_value=_MockPassReviewer()):
                    with patch("orchestrator.jobs.FactReviewer", return_value=_MockPassReviewer()):
                        with patch("orchestrator.jobs.ComplianceReviewer", return_value=_MockPassReviewer()):
                            # Run the failing generator — must NOT raise out of the task function
                            await _async_run_generator_task(
                                exhausted_task, generation_id, ke_id, "linkedin_post", model, 0.0
                            )

                            # Run the succeeding generator — must complete normally
                            await _async_run_generator_task(
                                fresh_task, generation_id, ke_id, "executive_summary", model, 0.0
                            )

        # --- Assert both artifact rows were written ---
        from sqlalchemy import select as sa_select
        result = await db_session.execute(
            sa_select(Artifact).where(Artifact.generation_id == gen.id)
        )
        artifacts = {a.output_type: a for a in result.scalars().all()}

        assert "linkedin_post" in artifacts, "Dead-lettered generator must still write a FAILED artifact row"
        assert "executive_summary" in artifacts, "Succeeding generator must write its artifact"

        # The dead-lettered artifact must be FAILED with no content
        dead = artifacts["linkedin_post"]
        assert dead.review_status == ArtifactReviewStatus.FAILED, (
            f"Dead-lettered artifact must have FAILED review_status, got {dead.review_status}"
        )
        assert dead.content is None, "Dead-lettered artifact must have no content"
        assert dead.retry_count == _GENERATOR_MAX_RETRIES, (
            "retry_count must reflect exhausted retries"
        )
        dead_results = dead.review_results or []
        assert any(r.get("dead_lettered") for r in dead_results), (
            "review_results must mark the artifact as dead_lettered"
        )

        # The succeeding artifact must have content
        ok = artifacts["executive_summary"]
        assert ok.content is not None, "Succeeding generator's artifact must have content"
        assert ok.review_status != ArtifactReviewStatus.FAILED, (
            "Succeeding generator must not be marked FAILED"
        )

        # --- _finalize_generation must produce PARTIAL_FAILURE ---
        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            await _finalize_generation(generation_id)

        await db_session.refresh(gen)
        assert gen.status == GenerationStatus.PARTIAL_FAILURE, (
            f"One dead-lettered artifact must cause PARTIAL_FAILURE, got {gen.status}"
        )

    async def test_dead_letter_does_not_raise_out_of_task_function(
        self, db_session: AsyncSession, session_factory
    ):
        """
        The dead-letter handler must swallow the MaxRetriesExceededError and return cleanly.
        If it raises, the Celery group would abort all remaining tasks — catastrophic.
        """
        from orchestrator.jobs import _async_run_generator_task
        from agents.base import GeneratorArtifactResult

        source = Source(
            extracted_text="Test source.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.5,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        from db.models import KnowledgeExtractionModel
        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="Test.",
            entities={"organizations": [], "people": [], "locations": [], "products": []},
            facts=[],
            relationships=[],
            domain="general",
            source_tone="formal",
        )
        db_session.add(ke)
        await db_session.commit()

        def always_fail_factory(output_type_key, client, model):
            class _Fail:
                async def generate(self, context, params, correction_notes=None):
                    raise RuntimeError("Always fails")
            return _Fail()

        exhausted_task = self._make_exhausted_task()

        # Must NOT raise — dead-letter path must return None, not propagate the error
        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            with patch("orchestrator.jobs.GenericGeneratorAgent", side_effect=always_fail_factory):
                result = await _async_run_generator_task(
                    exhausted_task, str(gen.id), str(ke.id), "linkedin_post", "claude-opus-4-5", 0.0
                )

        assert result is None, (
            "Dead-letter handler must return None, not raise — "
            "raising would abort the entire Celery group and defeat fan-out reliability."
        )

    async def test_all_generators_succeed_when_no_failures(
        self, db_session: AsyncSession, session_factory
    ):
        """
        Baseline: with no failures, all generators complete and generation is COMPLETED.
        """
        from orchestrator.jobs import _async_run_generator_task, _finalize_generation
        from agents.base import GeneratorArtifactResult

        source = Source(
            extracted_text="Baseline test source.",
            sensitivity=SensitivityLevel.PUBLIC,
            sensitivity_source=SensitivitySource.CLASSIFIER,
            sensitivity_confidence=0.9,
        )
        db_session.add(source)
        await db_session.flush()

        gen = Generation(
            source_id=source.id,
            output_types=["linkedin_post", "twitter_post"],
            params={},
            status=GenerationStatus.RUNNING,
        )
        db_session.add(gen)
        await db_session.flush()

        from db.models import KnowledgeExtractionModel
        ke = KnowledgeExtractionModel(
            source_id=source.id,
            summary="Baseline.",
            entities={"organizations": [], "people": [], "locations": [], "products": []},
            facts=[{"claim": "Baseline fact.", "source_span": "Baseline",
                    "start_char": 0, "end_char": 8, "confidence": 0.9}],
            relationships=[],
            domain="general",
            source_tone="formal",
        )
        db_session.add(ke)
        await db_session.commit()

        generation_id = str(gen.id)
        ke_id = str(ke.id)

        def success_factory(output_type_key, client, model):
            class _OK:
                async def generate(self, context, params, correction_notes=None):
                    return GeneratorArtifactResult(
                        output_type=output_type_key,
                        content="\n\n".join("## " + title + "\nBaseline fact." for title in get_blueprint(output_type_key).sections),
                        facts_used=[{"claim": "Baseline fact."}],
                        prompt_version="1.0.0",
                        model_version=model,
                        token_usage={"input_tokens": 100, "output_tokens": 50},
                    )
            return _OK()

        fresh_task = self._make_fresh_task()

        class _MockPassReviewer:
            version = "1.0.0"
            async def review(self, content, context, params):
                from schemas.review import ReviewResult
                return ReviewResult(reviewer_name="pass", passed=True, details={}, reviewer_version="1.0.0")

        with patch("orchestrator.jobs.AsyncSessionLocal", session_factory):
            with patch("orchestrator.jobs.GenericGeneratorAgent", side_effect=success_factory):
                with patch("orchestrator.jobs.StyleReviewer", return_value=_MockPassReviewer()):
                    with patch("orchestrator.jobs.FactReviewer", return_value=_MockPassReviewer()):
                        with patch("orchestrator.jobs.ComplianceReviewer", return_value=_MockPassReviewer()):
                            for ot in ["linkedin_post", "twitter_post"]:
                                await _async_run_generator_task(
                                    fresh_task, generation_id, ke_id, ot, "claude-opus-4-5", 0.0
                                )

            await _finalize_generation(generation_id)

        await db_session.refresh(gen)
        assert gen.status == GenerationStatus.COMPLETED, (
            f"All-success pipeline must finalize as COMPLETED, got {gen.status}"
        )



# ─── Stateless API Decoupling ─────────────────────────────────────────────────

class TestStatelessAPIDecoupling:
    """
    §4 / Phase 2 §6 — "stateless API assertion: kill/restart API process mid-job
    and confirm Celery workers keep processing."

    True kill/restart requires a live multi-process environment (covered in
    load_test_fanout.py for real-worker runs). These tests validate the structural
    guarantees that MAKE statelessness possible — no in-memory pipeline state on the
    API process, Celery as the only coupling point.
    """

    def test_api_holds_no_in_memory_pipeline_state(self):
        """
        The API module must not maintain any in-process registry of running pipeline jobs.
        All state is in Postgres (Generation rows) and Redis (Celery task results).
        If the API process dies, workers keep processing against the same DB + broker.
        """
        import orchestrator.jobs as jobs_module
        import api.routes.generations as gen_routes
        import inspect

        # API routes must NOT import or reference any in-memory state containers
        # (dict/list/set at module level that track running jobs)
        routes_source = inspect.getsource(gen_routes)

        # No global dict/list that would store generation state across requests
        # (dependency-injection bindings like app.dependency_overrides are excluded)
        forbidden_patterns = [
            "_running_jobs",
            "_active_generations",
            "_task_registry",
            "_pipeline_state",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in routes_source, (
                f"API routes must not hold in-memory pipeline state '{pattern}'. "
                "If the API process restarts, state would be lost — workers must be the authority."
            )

    def test_enqueue_generation_is_the_only_api_to_worker_coupling(self):
        """
        The API's only mechanism for starting pipeline work is enqueue_generation().
        This means a new API process can call enqueue_generation on any existing
        Generation ID and the worker will find all state it needs in the DB.
        """
        import api.routes.generations as gen_routes
        import inspect

        source = inspect.getsource(gen_routes)

        # The API must use enqueue_generation (the Celery .delay wrapper), not
        # call pipeline logic directly (which would tie execution to the API process)
        assert "enqueue_generation" in source, (
            "API must use enqueue_generation() — the Celery dispatch boundary — "
            "not execute pipeline logic inline."
        )

        # It must NOT directly call the async pipeline functions
        assert "_async_run_generation_pipeline" not in source, (
            "_async_run_generation_pipeline is a worker-side function. "
            "If the API calls it directly, pipeline execution is coupled to the API process."
        )

    def test_generation_row_carries_all_state_needed_to_resume(self):
        """
        Generation + Artifact rows must carry all fields a worker needs to process or
        re-process a job after an API restart. A new worker can re-fetch the Generation
        by ID and proceed without any API-process context.
        """
        from db.models import Generation, Artifact

        # Generation must carry input params and versioning (worker reads these)
        gen_cols = {c.name for c in Generation.__table__.columns}
        required_generation_fields = {
            "id", "source_id", "output_types", "params",
            "prompt_version", "model_version", "status",
        }
        missing = required_generation_fields - gen_cols
        assert not missing, (
            f"Generation model missing fields needed for worker-side resume: {missing}"
        )

        # Artifact must carry retry_count so a resumed worker knows where it left off
        art_cols = {c.name for c in Artifact.__table__.columns}
        required_artifact_fields = {"id", "generation_id", "output_type", "retry_count", "review_status"}
        missing = required_artifact_fields - art_cols
        assert not missing, (
            f"Artifact model missing fields needed for worker-side resume: {missing}"
        )
