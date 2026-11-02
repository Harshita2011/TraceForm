# Phase 6 — Multiple-source synthesis

Implemented and verified locally on 2026-11-01. Hosted release and real-provider acceptance are not claimed.

## Workflow

Use **Create output → Combine documents**. Select 2–8 ready documents (up to 200,000 combined extracted characters), optionally save a collection, then start an explicitly budgeted source analysis. Each document is extracted separately. Identical normalized claims retain references to every supporting document. Numerical and model-detected semantic conflicts appear before output creation.

Inspect facts and exact source passages. For each conflict, keep both accounts with uncertainty, omit disputed claims, or explicitly prefer a supporting source while noting the discrepancy. Analysis and output generation have separate budgets. Completed analyses reopen without another analysis call. Collections support revision-checked updates and archive/restore; edits cannot change existing run snapshots.

The output view records all source versions and decisions. Evidence filters by document. Passage requests bind document ID, generation and expected version; unmatched passages return an error without a substitute quote. Saved-version reviews, retries, regeneration and exports retain the manifest and conflict rules.

## Persistence and access

Additive migration `0007_multiple_sources` introduces source collections, generation document snapshots, source analysis and optional extraction/conflict metadata. Collections, analyses and new combined runs are operator-private. Source-library access still follows the existing shared API-key model; workspace/document ACLs remain Phase 7.

Strictest source sensitivity applies throughout the run. Changed, removed or unavailable secondary sources block execution, evidence and export. Secondary-source deletion is protected like primary-source deletion. Analysis uses the durable queue, explicit usage budgets, idempotency, cancellation and extraction checkpoints. The server stamps provenance after discarding model-provided authority fields. Deterministic reviewers check recorded citations against conflict choices; semantic reviewers inspect the output and conflict register.

## Verification

| Check | Result |
| --- | --- |
| Full native SQLite suite | 430 passed, 4 skipped: 3 PostgreSQL-only and native PDF dependency |
| Full native PostgreSQL 18 suite | 433 passed, 1 native PDF dependency skip |
| Phase 6 suite with saved-version review coverage | 10 passed |
| Frontend tests | 25 passed |
| ESLint, TypeScript, production build | Passed |
| PostgreSQL production-profile smoke | Passed on isolated retry: repeated migrations, API restart during generation, independent worker, idempotency, cancellation, encrypted credentials, 5 local HTTP provider calls / 150 tokens |
| Browser workflow | Collection save, separate analysis, 3 deduplicated facts / 2 documents, conflict controls, preferred-source gate, exact passages, back-navigation retention, combined generation, source filtering, second-document citation, analysis reopen |
| Responsive UI | Phone 390×844 and tablet 820×1180: no horizontal overflow; screenshots saved and inspected |
| Data preservation | Every original business row compared across all original columns and unchanged; 23 sources, 38 generations, 51 artifacts retained; no Phase 6 fixtures in actual DB |
| Normal app | SQLite migrated to 0007; API, independent worker and frontend restored; readiness HTTP 200 |

The full SQLite checkpoint preceded the added saved-version assertions. Those passed in the targeted suite and subsequent complete PostgreSQL suite. The first production smoke exceeded its 15-second worker-start wait while other verification was active; the unchanged isolated retry passed. Browser verification used a separate SQLite database and local HTTP mock, then returned to the normal workspace.

Runtime evidence: `.runtime/phase6-postgres-smoke.json`, `.runtime/phase6-preservation.json`, and screenshots under `frontend/.visual-check/phase6-*.png`. These are ignored verification artifacts.

## Remaining acceptance boundaries

- The initial Docker startup blocker was cleared on 2 November 2026. The current image passed the full PostgreSQL and SQLite suites, production API restart, outage readiness and container/storage persistence checks, including the Phase 6 tests. See the Docker follow-up in [PHASE7_VERIFICATION.md](PHASE7_VERIFICATION.md).
- Real-provider end-to-end acceptance remains pending. One development sensitivity test accidentally reached Gemini with synthetic text `Public-facing text` and returned HTTP 200; no user documents were sent. Its billing amount was not established. This is not acceptance evidence. The test was isolated, the test Gemini key is now cleared, and non-local provider TCP connections are blocked.
- Deduplication uses normalized exact claims, not universal semantic equivalence. Conflict detection can miss differences or flag distinct scopes. Operators must inspect important claims. Anchor checks confirm location, not factual truth.
- Selections over 8 documents or 200,000 extracted characters are rejected without silent truncation. Team authentication, document ACLs, approvals and collaborative audit workflows remain Phase 7.
