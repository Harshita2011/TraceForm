# Phase 4 — evidence and review

Implemented 31 October 2026. Local automated and isolated browser checks are recorded
in FEATURE_LEDGER.md. A successful live-provider acceptance run remains pending:
the configured Gemini model returned intermittent 503 high-demand and 504 deadline
errors. These failures were retained and never displayed as verified outputs.

## Behavior

- Every recorded source reference is checked against exact text and Unicode character
  offsets. Source IDs, SHA-256 source/content versions and stable passage IDs are retained.
- Analyst offsets may be corrected only when the exact quote occurs once in the source.
  The original model offsets and `unique_quote` resolution are retained and explained in
  source details. Missing quotes and ambiguous references with invalid offsets fail.
- Source facts, explicitly labeled recommendations, derived calculations and unsupported
  statements have separate reference states. Calculations require cited inputs and exact
  decimal arithmetic; supported operations are sum, difference, product, ratio and percent
  change. Inputs are plain decimal values; only percent-change results may carry a
  percent symbol. Rounded results and implicit unit conversions are rejected.
  Arithmetic checks do not establish that the source quantities have compatible units;
  semantic review and user inspection are still required.
  The source panel exposes the declared operation, input values and result. Translated
  proposal/calculation labels are supported; their meaning is assessed by the model
  reviewers, while the deterministic check verifies that the declared marker is visible.
- A quote matching its location does not prove that a generated claim follows from it.
  Numeric mismatches are checked deterministically; semantic support, invented entities,
  conflicting statements and uncited text also receive a model fact review.
- Style, fact, compliance, format and evidence checks gate a new output. Specialist
  format heuristics are labeled advisory. One correction attempt receives recorded
  failure feedback; both attempts and their content identities remain inspectable.
- Generated text is checkpointed as unreviewed before review begins. Saved drafts remain
  inspectable if subsequent review fails. Writes remain fenced to the owning worker.
- Feedback is attributed to the actual artifact/content version and recorded in an
  append-only audit row. Compliance exceptions require an administrator or reviewer,
  a meaningful reason and a recorded failed compliance check. The UI also requires an
  explicit acknowledgment and sends the content version to detect stale decisions.
- Exceptions retain failed checks, do not certify an output, and do not change source
  sensitivity. Historical exceptions with no matching content version cannot apply to
  a new version. The panel shows the latest 50 decisions; all events remain stored.

## Interface

Open **Evidence** on an output for Findings, Sources, Checks and Decisions. Findings
can highlight exact affected text; references open the correct source passage and
version. Technical identifiers and correction history use disclosures. Opening the
panel and locating text move keyboard focus to the destination. Desktop and 390-pixel
phone workflows were exercised without page-level horizontal overflow.

Local edits are labeled unreviewed. Original-version findings and decisions remain
explicitly scoped to the original; decision controls are disabled for the edited draft.
Draft storage is still browser-local until Phase 5.

The browser tests used `.runtime/phase4-ui.db`, an isolated SQLite database with clearly
labeled mock review fixtures. The normal API/worker were restored afterward. The
configured provider and normal saved database were not replaced by fixture settings.
All 22 original source IDs were retained; one fictional community-garden source was
added for real-provider verification.

## Boundaries

Reference counts describe recorded anchors, not total factual coverage or certified
accuracy. The model can miss a semantic error. This phase does not implement shared
editing, re-review of saved edits, workspace isolation, approval workflows or richer
exports. Those remain in Phases 5–8. It does not silently re-certify old outputs: missing
required checks or invalid references are shown as needing review.

The real-provider runs used only fictional facts and a USD 0.10 admission limit per
run. Known estimated usage totaled 17,306 tokens / USD 0.03887875 across three failed
runs; one review request had no recorded usage, so these are not asserted as the final
provider bill. No further paid retries were made after the provider failures.

Evidence is kept in `.runtime/phase4-*` and `.runtime/docker-verification/`.
Screenshots are under `frontend/.visual-check/phase4-*`. The additive migration is
`0005_review_evidence`; a snapshot was saved before live checks at
`traceform/storage_data/backups/phase4-before-live-checks-20261031-095236.db`.
