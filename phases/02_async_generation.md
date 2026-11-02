Building on Phase 1, add async job processing and complete the generator set.

1. CELERY + REDIS QUEUE (§4 Reliability, §5 architecture)
   - Wire Celery with Redis as broker + result backend, per docker-compose.
   - Convert POST /api/v1/generations to: create Generation row (status=queued) → enqueue an
     orchestrator task → return 202 with generation id immediately. GET /api/v1/generations/{id}
     reflects live status (queued → running → completed/partial_failure).
   - Retry + dead-letter handling: each Celery task (Analyst run, each Generator run) gets bounded
     retries with backoff; after retries exhausted, route to a dead-letter queue and mark that specific
     artifact/stage as failed WITHOUT failing the rest of the batch. Write a test that kills one
     generator task and asserts the other generators still complete and are delivered.
   - Orchestrator fan-out: after the Analyst Agent completes, enqueue all requested Generator Agent
     tasks in PARALLEL (not sequentially) — this is required for §4's fan-out latency claim
     (generator-stage latency ≈ max(generator latencies), not sum). Use Celery group/chord or
     equivalent; write a test asserting wall-clock time for N parallel generators is close to the
     slowest one, not the sum.

2. REMAINING GENERATORS — implement all 9 output types from §3.3:
   LinkedIn Post, Twitter/X, Advisory, Executive Summary, Presentation, Infographic, Video Package,
   Newsletter, Press Release.
   - Each gets its own versioned YAML config (output_type, prompt_template_version, output_json_schema,
     renderer) — no core code changes required to add a type, per §1.3 "extensible by configuration."
     Prove this: implement a generic GeneratorAgent class parameterized by YAML config, not 9 separate
     Python classes with duplicated logic.
   - Presentation and Video Package: Presentation renders to .pptx via python-pptx (§6) in the
     Assembly/Rendering stage (stub the Assembly stage now if not yet built — full rendering can be a
     small addition here). Video Package in V1 only packages script/storyboard text + references the
     attached video context from ingestion (§3.1) — it does NOT generate actual video.
   - Infographic: text/data-spec output only in V1 (no image generation implied by the PRD) — confirm
     this assumption in a code comment; treat it as structured content ready for a rendering layer.

3. GENERATION PARAMETERS (§3.4)
   - Implement audience, tone, language, detail_level, objective, style as a GenerationParams schema.
   - Support global params (set once per Generation) with per-output-type override (e.g.
     params.overrides["twitter"] = {tone: "punchy"}). Generators must merge global + override correctly
     — write a test for override precedence.

4. PROMPT / MODEL / REVIEWER VERSIONING (§3.5, reproducibility in §4)
   - Every Generation row pins prompt_version (derived from which YAML config versions were used across
     all requested output types), model_version (the exact Anthropic model string used), and
     reviewer_version (stub as "unset" until Phase 3 exists).
   - This must be captured automatically at generation time, not set manually — write a test that
     changes a YAML prompt_template_version and asserts a new Generation reflects the new version while
     an old Generation record's pinned version is unchanged (i.e. old generations remain reproducible
     even after config changes).

5. API additions
   - GET /api/v1/history (list generations, filterable by status/output_type/date — filtering logic only,
     no UI)
   - Update GET /api/v1/generations/{id} to reflect per-artifact async status.

6. TESTS
   - Unit test per new generator against fixed KnowledgeExtraction fixtures.
   - Load test (can be a locust/pytest-benchmark script, not necessarily CI-gated yet) simulating
     concurrent generations across multiple output types, asserting fan-out latency behavior from §4
     and that worker pool scaling is decoupled from API (stateless API assertion — kill/restart API
     process mid-job and confirm Celery workers keep processing).
   - Dead-letter / partial-failure test as described in #1.

Do not implement review agents yet (Phase 3) — artifacts are still delivered with review_status
pending/null. Do not implement cost tracking or budget enforcement yet (Phase 4).