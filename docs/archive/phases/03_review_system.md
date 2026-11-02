Building on Phase 2, implement the three-reviewer review layer and the Fact Reviewer's regeneration logic.

1. REVIEWER INTERFACE
   - Each reviewer implements review(artifact: Artifact, context: KnowledgeExtraction) -> ReviewResult
     from the Phase 0 interface. ReviewResult = {reviewer_name, passed: bool, details: dict,
     reviewer_version}.
   - Reviewers must be independent, side-effect-free checks — no reviewer may mutate the artifact or
     call another reviewer. Enforce this with a design that passes reviewers read-only copies.

2. THE THREE REVIEWERS, run CONCURRENTLY per artifact (§3.5) — after a Generator Agent produces an
   artifact, fan out Style + Fact + Compliance as parallel Celery tasks (same fan-out pattern as
   Phase 2's generator stage). Fan-out latency for this stage = max(reviewer latencies), not sum —
   write a test proving this, mirroring Phase 2's generator fan-out test.

   a) STYLE REVIEWER — checks tone/audience/objective adherence against the GenerationParams used
      for that artifact. Use an LLM-as-judge call with a structured pass/fail + reasoning output,
      validated against a fixed schema.

   b) FACT REVIEWER (§3.6) — the load-bearing one:
      - Compare each claim in the generated artifact against the cited facts in the KnowledgeExtraction
        (matched via the facts_used references the generator recorded, or by re-extracting claims from
        the artifact text and matching against context.facts).
      - A claim with NO supporting fact, or one that CONTRADICTS a cited fact (e.g. a changed number),
        fails review.
      - On failure: trigger exactly ONE bounded regeneration attempt. Feed the specific failing claim(s)
        back to the Generator Agent as targeted correction context (not a full re-run from scratch —
        pass the original context + params + a "correction_notes" field naming the failing claims).
      - SECOND-FAILURE PATH (this is new/important in the PRD, implement precisely):
        - If the regenerated artifact fails Fact Review again:
          1. Deliver the artifact anyway, but set review_status = "failed" (not silently passed).
          2. Attach the specific unresolved claim(s) to the artifact's review_results so they can be
             surfaced in the explainability panel later (Phase 4).
          3. This artifact must be EXCLUDED from any aggregate "fact accuracy passing" figure — but
             INCLUDED as a failure in whatever will feed the evaluation harness (Phase 5). Add a field/
             flag now (e.g. Artifact.counted_as_eval_failure = True) so Phase 5 doesn't need a schema
             change.
          4. Do NOT attempt a second automatic regeneration — bounded to one, per cost control in §4.
             Write a test asserting exactly one regeneration attempt occurs, never more.
        - retry_count on the Artifact model tracks this.

   c) COMPLIANCE REVIEWER — hard gate, checks:
      - Hate speech / unsafe content.
      - PII leakage.
      - Unverifiable high-risk claims.
      - Sensitivity-vs-output-type conflicts (e.g. an Internal-sensitivity source generating a public
        LinkedIn Post/Twitter artifact must be flagged) — this is a HARD gate per §7, not a warning.
      - Injection-pattern indicators in the GENERATED OUTPUT (§3.1.1): scan for signs the artifact
        itself claims elevated permissions, discloses system-prompt content, or contradicts its own
        sensitivity gating. Hard-fail the artifact if found — this is distinct from the input-side
        handling done in Phase 1; write a test where a generator's output (simulate this) leaks
        something like "SYSTEM PROMPT:" and assert Compliance hard-fails it.
      - Compliance failures do NOT get the Fact Reviewer's regenerate-once treatment — they hard-fail
        and require either operator fix of inputs or an explicit override (next point).

3. COMPLIANCE OVERRIDE (§3.10, §7, §5's ComplianceOverride model)
   - Add POST /api/v1/generations/{id}/artifacts/{type}/override accepting a required reason string.
   - Writes a ComplianceOverride row (artifact_id, operator_id, reason, created_at) and flips the
     artifact's delivery gating so it can be released despite the Compliance hard-fail.
   - This must NEVER be a silent bypass — every override is audit-logged by construction (the endpoint
     cannot succeed without persisting the ComplianceOverride row in the same transaction as the status
     change). Write a test that an override without a reason string is rejected (422).

4. SENSITIVITY GATING TIE-IN (§3.1.1)
   - Confirm operator-set sensitivity always overrides the classifier's suggestion when both exist —
     the Compliance Reviewer's sensitivity-conflict check must read sensitivity_source and treat
     operator-set as authoritative. Add a regression test using a case where classifier and operator
     disagree.

5. API updates
   - GET /api/v1/generations/{id}/artifacts/{type} now returns review_results (all three reviewers'
     outcomes) and review_status (passed|failed|budget_exceeded — budget_exceeded arrives in Phase 4).

6. TESTS
   - Full pipeline integration test: source → extraction → generation → all 3 reviewers → deliberate
     fact mismatch → single regeneration → still-failing case → second-failure path artifact delivered
     with review_status=failed and flagged claims.
   - Adversarial-output fixture for Compliance's injection scan.
   - Sensitivity-conflict fixture (Internal source → public-facing output type) asserting hard gate.
   - Override audit-log test.

Do not implement cost/budget tracking yet (Phase 4) or the evaluation harness (Phase 5).