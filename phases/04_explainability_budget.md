Building on Phase 3, implement cost tracking, the hard budget cap with its defined exceeded-budget
behavior, the explainability data, and feedback.

1. TOKEN USAGE & COST TRACKING (§3.7)
   - Every LLM call (Analyst, each Generator, each Reviewer) must record input/output token counts and
     a computed cost (use a configurable $/token table per model, not hardcoded, since pricing changes).
   - Aggregate per-artifact cost = its own generation call + its share of the Analyst call (decide and
     document an attribution method, e.g. Analyst cost divided across all output_types in that
     Generation) + any regeneration + all 3 reviewer calls for that artifact. Store as Artifact.cost JSON
     with a breakdown (not just a total) — {analyst_share, generation, regeneration, style_review,
     fact_review, compliance_review, total}.
   - Write a test asserting a regenerated artifact's cost includes both generation attempts.

2. HARD BUDGET CAP (§4 — implement EXACTLY as specified, this resolves a previously-ambiguous behavior)
   - Each Generation has a fixed LLM-call budget (token + call-count ceiling), set at account/config
     level, stored as Generation.budget_ceiling; running total tracked in Generation.budget_used,
     updated atomically after each LLM call.
   - If a generation would exceed budget mid-run (e.g. many output types + regenerations):
     a) Already-completed artifacts are still delivered normally — do not roll them back or block them.
     b) Remaining not-yet-started artifacts are marked status="budget_exceeded" — NOT silently skipped,
        NOT queued indefinitely. This must be a distinct, visible terminal state.
     c) The API must expose exactly which output types were skipped for this reason (list them in the
        Generation status response).
     d) Add POST /api/v1/generations/{id}/artifacts/{type}/rerun — re-running a skipped type starts a
        FRESH budget allocation scoped to just that rerun (not shared with the original generation's
        exhausted budget). Write a test: exhaust budget with 3 of 5 output types skipped, rerun one,
        assert it succeeds under its own fresh budget even though the original Generation's budget_used
        is still over ceiling.
     e) Critical constraint — write an explicit test for this: no generation may silently truncate or
        degrade output quality to fit under budget. The budget gates WHICH artifacts run, never HOW WELL
        each one is done. If this constraint is at risk of being violated by any optimization, fail the
        artifact and mark budget_exceeded instead of shortening its prompt/output.

3. EXPLAINABILITY PANEL DATA (§3.7) — this phase makes it real, not just asserted. Every delivered
   artifact's API representation must carry:
   - facts_used: each fact's claim + source citation (source_span, start_char, end_char) + confidence,
     pulled from the KnowledgeExtraction facts the generator actually cited.
   - Reviewer pass/fail record including regeneration history and its outcome (from Phase 3's
     review_results, now surfaced fully).
   - Token usage + cost breakdown (from #1 above).
   - prompt_version, model_version, reviewer_version pinned at generation time (from Phase 2).
   - Sensitivity provenance: sensitivity_source (operator|classifier) + sensitivity_confidence, plus
     any ComplianceOverride applied (reason, operator_id, timestamp) from Phase 3.
   - Ensure GET /api/v1/generations/{id}/artifacts/{type} returns ALL of the above in one response —
     write a schema test that fails if any of these fields is missing or null when it shouldn't be.

4. HUMAN FEEDBACK (§3.9)
   - POST /api/v1/generations/{id}/artifacts/{type}/feedback accepting thumbs up/down (+ optional
     comment), stored against Artifact.feedback and tagged with the generation/prompt version that
     produced it (so feedback remains meaningful even after prompt versions change).
   - This is explicitly a lightweight defensibility mechanism per the PRD, not an ML feedback loop —
     do not build any retraining/analysis pipeline here, just capture and store correctly.

5. REMAINING §3.11 ENDPOINTS
   - GET /api/v1/metrics — request rate, failure rate, per-stage latency, token usage/cost (feed from
     OpenTelemetry/structured logs set up in Phase 5, stub with real DB aggregation for now if
     OTel isn't wired yet).
   - Confirm all mutating endpoints (sources, generations, override, feedback, rerun) require API-key
     auth (basic version now; full auth hardening is Phase 5) and are rate-limited (basic in-memory or
     Redis-backed limiter now).

6. TESTS
   - Budget-exceeded end-to-end test per #2.
   - Explainability completeness test per #3.
   - Feedback persistence + version-tagging test.
   - Cost breakdown accuracy test with a mocked known token count, asserting the computed cost matches
     hand-calculated expected cost.

Do not build the evaluation harness or OpenTelemetry tracing yet (Phase 5). Do not build the dashboard.