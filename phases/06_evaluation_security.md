Building on Phase 4, implement evaluation, full observability, and CI hardening — this is the phase
that turns the PRD's quality claims into "measured, not asserted" (§1.3).

1. EVALUATION HARNESS (§3.8)
   - Build a maintained evaluation dataset structure: ~20 sources per domain (incident reports, policy
     documents, news articles) — create the dataset directory format + loader, and a small real seed
     set (even 3-5 sources per domain is fine to start; document that reaching ~20 is a data task, not
     a code task).
   - Offline/CI scoring script (eval/run_eval.py) that runs the full pipeline (ingestion → extraction →
     all requested generators → all 3 reviewers, including regeneration) against the eval set and
     computes:
     - Fact Accuracy: claims verified against citations, EXPLICITLY including second-failure artifacts
       counted as failures (per §3.6's counted_as_eval_failure flag from Phase 3) — do not let these
       artifacts silently count as passes.
     - Style Adherence: Style Reviewer pass rate.
     - Latency: per-stage and end-to-end, p50/p95.
     - Cost per artifact: from Phase 4's cost tracking.
   - Persist results as an EvaluationRun row (dataset_version, dataset_size, fact_accuracy,
     style_adherence_rate, avg_latency, avg_cost, created_at).
   - GET /api/v1/evaluations/latest must return the numbers ALONGSIDE dataset_size in the same
     payload — never numbers without the sample size next to them (this is a stated PRD principle,
     §3.8/§10: figures are directional, not certified). Write a test that the endpoint 400s or omits
     numbers if dataset_size isn't attached.
   - Wire this script to run in CI (see #4).

2. OBSERVABILITY (§4)
   - OpenTelemetry tracing: propagate source_id and generation_id through every span (ingestion,
     Analyst call, each Generator call, each Reviewer call, Assembly/Rendering). Set up an OTel
     Collector target in docker-compose (can point to a local Jaeger/console exporter for the demo).
   - Structured logging (JSON logs) at each pipeline stage with source_id/generation_id correlation.
   - Wire real data into GET /api/v1/metrics (stubbed in Phase 4): request rate, failure rate,
     per-stage latency, token usage/cost — pull from OTel metrics or DB aggregation, whichever is
     already available; document the choice.

3. SECURITY HARDENING (§7)
   - Confirm secrets are only ever read from env/secrets manager — grep-test that no API keys or
     secrets appear as string literals anywhere in the codebase.
   - Full API-key auth: scoped per operator (not a single shared key) — add an operators table/config
     if not already present, and ensure every mutating endpoint resolves and logs which operator made
     the call (needed for ComplianceOverride.operator_id and feedback attribution to be meaningful,
     not just placeholder strings).
   - Rate limiting per API key (upgrade Phase 4's basic limiter to be properly per-key and configurable).
   - Full audit log: confirm generations, reviewer outcomes, and overrides are all queryable via a
     single audit trail (can be a DB view/query over existing tables — Generation, Artifact.review_results,
     ComplianceOverride — rather than a new table, if that already captures everything required).

4. TESTING & CI (§8) — assemble everything from prior phases into a real CI pipeline
   - Unit tests per generator/reviewer against fixed knowledge-extraction fixtures (should already
     exist from Phases 1–3 — confirm coverage, fill gaps).
   - Contract tests: every generator/reviewer output validated against its JSON schema in CI (wire
     Phase 0's Pydantic schemas into an explicit CI-gated test job).
   - Integration test: full pipeline against a small fixed sample corpus, INCLUDING adversarial-input
     fixtures from Phase 1 (sources with embedded instruction-like text) — confirm this runs in CI, not
     just locally.
   - Load test: concurrent generations × multiple output types, verifying fan-out latency claims from
     Phases 2 and 3 and worker scaling — can be CI-gated with relaxed thresholds (exact numbers vary by
     CI hardware) or run as a separate nightly job; document the choice.
   - Evaluation harness scoring run in CI (from #1), with results published as a CI artifact (e.g. a
     JSON/markdown summary attached to the build) so eval numbers are visible without a manual step.
   - Write a GitHub Actions (or equivalent) workflow file wiring: lint → unit → contract → integration
     (incl. adversarial) → eval scoring, in that order, failing fast.

5. FINAL NON-FUNCTIONAL VERIFICATION PASS
   - Reliability: confirm a killed worker mid-job still lets the rest of the batch complete (should
     already be tested in Phase 2 — re-run/confirm with full pipeline now including reviewers).
   - Performance: assert against the p95 targets in §4 (Analyst <10s, each generator <15s, each
     reviewer <8s) as CI-visible (not hard-failing) benchmarks, since these depend on the live model API.
   - Reproducibility: pick one delivered Generation, change nothing, re-fetch its artifacts, and assert
     prompt_version/model_version/reviewer_version are identical even after later code changes to
     current YAML configs (i.e. old records are genuinely frozen, not just labeled).

Deliverable at the end of this phase: `docker-compose up` brings up a fully working backend (API +
worker + Postgres + Redis + OTel collector) that can take a source through ingestion → extraction →
9 parallel generators → 3 concurrent reviewers with regeneration → budget-aware delivery →
explainability/cost data → feedback capture, and can be scored against the eval harness on demand
or in CI — matching §5's architecture diagram end to end, backend side.