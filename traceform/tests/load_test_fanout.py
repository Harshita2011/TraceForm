"""
# Phase 2 §6 Load Test — Fan-Out Latency & Stateless API Validation

NOT CI-gated by default (see phases/02_async_generation.md §6).
Run manually or in a dedicated nightly job.

    pytest tests/load_test_fanout.py -v -s

This file covers two distinct verification targets:

1. ASYNC FAN-OUT TIMING (Section A)
   Tests that N concurrent async generators take approx. max(individual latencies), not sum.
   Runs entirely in-process using asyncio.gather — no real Celery workers or broker needed.
   This validates the async concurrency model that underpins the Celery group dispatch.

2. STATELESS API / WORKER DECOUPLING (Section B)
   Documents and partially automates the "kill/restart API process mid-job" scenario.
   The structural guarantees are unit-tested in test_async_pipeline.py
   (TestStatelessAPIDecoupling). The live multi-process test described here requires
   a real Redis broker + Celery worker and is documented as a manual procedure.

------------------------------------------------------------------------
REAL-WORKER LOAD TEST INSTRUCTIONS (run against actual infrastructure)
------------------------------------------------------------------------

Prerequisites:
  docker-compose up redis postgres        # broker + DB
  celery -A orchestrator.celery_app worker --loglevel=info -c 4  # 4 worker slots

Run the fan-out latency scenario:
  TRACEFORM_LOAD_TEST=1 pytest tests/load_test_fanout.py::TestRealWorkerLoadTest -v -s

Stateless API kill/restart test (manual):
  1. POST a generation with 9 output types (all YAML types) -> note the generation_id
  2. Immediately kill the API process (Ctrl-C or kill -9 <api-pid>)
  3. Verify workers are still processing: check Celery logs / GET from a new API process
  4. Restart API: uvicorn api.main:app --port 8000
  5. GET /api/v1/generations/{generation_id} -- status must progress normally
  6. Assert all artifacts arrive (none missing due to API restart)

Expected: The API restart is transparent to the worker pipeline. All 9 artifacts
arrive because workers hold all necessary state (Generation row in Postgres, task
routing in Redis) -- none of it in the API process memory.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest


# ---- Section A: Async Fan-Out Timing ----------------------------------------

class TestAsyncFanOutLatency:
    """
    §4 -- Generator fan-out latency must equal max(generator latencies), not sum.

    These tests validate the asyncio concurrency model that the Celery group relies on.
    True multi-process parallelism is covered by the real-worker instructions above.

    Design: replace real generators with async sleeps of known duration. Measure total
    wall time for asyncio.gather (fan-out) vs. sequential awaiting.
    """

    GENERATOR_SLEEP_SECONDS = 0.08   # 80 ms per fake generator
    NUM_GENERATORS = 5
    # Fan-out must complete within 2.5x the single-generator time (generous tolerance for CI)
    FANOUT_MAX_MULTIPLE = 2.5

    async def _fake_generator(self, output_type: str, sleep: float) -> dict:
        """Simulate a generator that takes `sleep` seconds to run."""
        await asyncio.sleep(sleep)
        return {"output_type": output_type, "content": f"Generated {output_type}"}

    async def test_fanout_faster_than_sequential(self):
        """
        asyncio.gather (fan-out) must complete in approx. 1 generator time.
        Sequential await must take approx. N x generator time.
        Ratio must be < FANOUT_MAX_MULTIPLE (generous to avoid flaky CI).
        """
        sleep_time = self.GENERATOR_SLEEP_SECONDS
        output_types = [f"type_{i}" for i in range(self.NUM_GENERATORS)]

        # Sequential execution (worst case)
        t0 = time.perf_counter()
        sequential_results = []
        for ot in output_types:
            result = await self._fake_generator(ot, sleep_time)
            sequential_results.append(result)
        sequential_time = time.perf_counter() - t0

        # Fan-out execution (asyncio.gather)
        t0 = time.perf_counter()
        fanout_results = await asyncio.gather(
            *[self._fake_generator(ot, sleep_time) for ot in output_types]
        )
        fanout_time = time.perf_counter() - t0

        assert len(sequential_results) == self.NUM_GENERATORS
        assert len(fanout_results) == self.NUM_GENERATORS

        assert fanout_time < sequential_time, (
            f"Fan-out ({fanout_time:.3f}s) must be faster than sequential ({sequential_time:.3f}s)."
        )

        single_gen_time = sleep_time
        assert fanout_time < single_gen_time * self.FANOUT_MAX_MULTIPLE, (
            f"Fan-out time ({fanout_time:.3f}s) exceeded {self.FANOUT_MAX_MULTIPLE}x "
            f"single-generator time ({single_gen_time:.3f}s). "
            "Total latency must approximate max(generator latencies), not sum."
        )

    async def test_fanout_total_time_bounded_by_slowest_generator(self):
        """
        §4 -- 'generator-stage latency approx. max(generator latencies)'.

        One slow generator (200 ms), four fast (20 ms).
        Fan-out must finish in approx. 200 ms (the slowest), not 280 ms (sum of all).
        """
        SLOW = 0.20
        FAST = 0.02
        TOLERANCE = 1.8

        tasks = [
            self._fake_generator("slow_type", SLOW),
            self._fake_generator("fast_type_1", FAST),
            self._fake_generator("fast_type_2", FAST),
            self._fake_generator("fast_type_3", FAST),
            self._fake_generator("fast_type_4", FAST),
        ]

        t0 = time.perf_counter()
        results = await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - t0

        assert len(results) == 5
        assert elapsed < SLOW * TOLERANCE, (
            f"Fan-out took {elapsed:.3f}s but should be bounded by slowest generator "
            f"({SLOW}s x {TOLERANCE} tolerance = {SLOW * TOLERANCE:.3f}s). "
            f"Sum of all latencies would be {SLOW + 4 * FAST:.3f}s."
        )

    async def test_generator_failures_do_not_cancel_sibling_tasks(self):
        """
        §4 reliability -- when one generator raises, the others must still complete.
        asyncio.gather with return_exceptions=True mirrors the Celery group pattern.
        """
        GOOD_TYPES = ["type_a", "type_b", "type_c"]
        FAIL_TYPE = "type_fail"

        async def failing_generator(output_type: str) -> dict:
            await asyncio.sleep(0.02)
            raise RuntimeError(f"Simulated failure in {output_type}")

        tasks = [self._fake_generator(ot, 0.02) for ot in GOOD_TYPES]
        tasks.append(failing_generator(FAIL_TYPE))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == len(GOOD_TYPES), (
            f"All {len(GOOD_TYPES)} good generators must complete despite one failure."
        )
        assert len(failures) == 1
        assert isinstance(failures[0], RuntimeError)

    async def test_celery_group_dispatch_structure_in_orchestrator(self):
        """
        Structural validation: the orchestrator fan-out uses Celery group().
        """
        import orchestrator.jobs as jobs
        import inspect

        source = inspect.getsource(jobs._async_run_generation_pipeline)
        assert "group(" in source, (
            "Orchestrator must use Celery group() for fan-out. "
            "Sequential dispatch would make total latency = sum(latencies)."
        )


# ---- Section B: Stateless API Structural Checks ----------------------------

class TestStatelessAPIStructural:
    """
    Complement to TestStatelessAPIDecoupling in test_async_pipeline.py.
    Runtime-flavoured assertions that the API process holds zero pipeline state.
    """

    def test_api_app_has_no_module_level_task_state(self):
        """
        Importing the API app must not initialise any in-memory job state.
        """
        import api.main
        import api.routes.generations

        forbidden_attrs = [
            "running_jobs", "task_cache", "job_state",
            "active_pipelines", "generation_cache",
        ]
        for attr in forbidden_attrs:
            assert not hasattr(api.main.app, attr), (
                f"FastAPI app must not hold '{attr}' -- lost on restart."
            )
            assert not hasattr(api.routes.generations, attr), (
                f"generations module must not hold '{attr}' at module level."
            )

    def test_worker_can_find_all_needed_state_from_generation_id_alone(self):
        """
        The Celery task signature takes only generation_id.
        Everything the worker needs is in the DB, not passed from the API process.
        """
        import orchestrator.jobs as jobs
        import inspect

        task_source = inspect.getsource(jobs.run_generation_pipeline)
        assert "generation_id" in task_source

        async_source = inspect.getsource(jobs._async_run_generation_pipeline)
        assert "db.get" in async_source, (
            "Worker must re-fetch Generation from DB -- "
            "API restart must not affect the worker."
        )


# ---- Section C: Real-Worker Load Test (manual, skipped by default) ----------

@pytest.mark.skipif(
    not os.getenv("TRACEFORM_LOAD_TEST"),
    reason=(
        "Real-worker load test skipped. "
        "Set TRACEFORM_LOAD_TEST=1 with live Redis + Celery worker. "
        "See module docstring for full instructions."
    ),
)
class TestRealWorkerLoadTest:
    """
    Live load test against real Celery workers.
    Requires: TRACEFORM_LOAD_TEST=1, Redis running, Celery worker running.

    Run: TRACEFORM_LOAD_TEST=1 pytest tests/load_test_fanout.py::TestRealWorkerLoadTest -v -s
    """

    async def test_nine_generator_fanout_latency_within_bound(self):
        """
        POST a generation with all 9 output types.
        Assert it completes within 40s (2x p95 per generator + pipeline overhead).
        Wall time must be bounded by max(latencies), not sum(latencies).
        """
        import httpx

        api_url = os.getenv("TRACEFORM_API_URL", "http://localhost:8000")
        api_key = os.getenv("TRACEFORM_API_KEY", "dev-key")
        headers = {"X-API-Key": api_key}

        ALL_NINE = [
            "linkedin_post", "twitter_post", "advisory", "executive_summary",
            "presentation", "infographic", "video_package", "newsletter", "press_release",
        ]

        async with httpx.AsyncClient(base_url=api_url, headers=headers, timeout=30) as client:
            ingest = await client.post(
                "/api/v1/sources/",
                data={"text": "Apple Inc reported Q3 2024 revenue of $85.8 billion. "
                              "Strong iPhone and services growth drove the result."},
            )
            assert ingest.status_code == 200, f"Ingest failed: {ingest.text}"
            source_id = ingest.json()["id"]

            t0 = time.perf_counter()
            gen_resp = await client.post(
                "/api/v1/generations/",
                json={"source_id": source_id, "output_types": ALL_NINE},
            )
            assert gen_resp.status_code == 202, f"Generation POST failed: {gen_resp.text}"
            gen_id = gen_resp.json()["id"]

            MAX_WAIT = 120
            POLL_INTERVAL = 2.0
            elapsed = 0.0
            final_status = None

            while elapsed < MAX_WAIT:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                status_resp = await client.get(f"/api/v1/generations/{gen_id}")
                final_status = status_resp.json().get("status")
                if final_status in ("completed", "partial_failure", "failed"):
                    break

            total_wall_time = time.perf_counter() - t0

        # §4 bound: generator stage approx. max(latency); p95 per gen < 15s, allow 2x + overhead
        assert total_wall_time < 40.0, (
            f"Nine-generator fan-out took {total_wall_time:.1f}s -- "
            f"must be bounded by max(latencies), not sum. Final status: {final_status}"
        )
        assert final_status in ("completed", "partial_failure"), (
            f"Generation must reach terminal state, got '{final_status}' "
            f"after {total_wall_time:.1f}s."
        )
