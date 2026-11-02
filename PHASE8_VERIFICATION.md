# Phase 8 — evaluation, operations and release verification

Verified locally on 2 November 2026. Phase 8 implements measured evaluation, operations, encrypted recovery and release configuration. Live hosting is deferred by the user. A fully verified live-provider output remains an open release gate; generated drafts and failed provider calls are preserved honestly.

## Implemented behavior

| Capability | Persistence and UI |
| --- | --- |
| Versioned datasets | Immutable dataset names/versions, cases bound to exact saved output/source hashes, human claim verdicts/reasons/exact source quotes and optional style judgments. Owners/editors curate; workspace members inspect. Legacy API-key evidence remains operator-private. |
| Durable execution | Database queue, stable request IDs, cancellation, per-case checkpoints, interrupted-worker recovery and inspectable unavailable-source outcomes. Scoring human assessments makes no provider calls. |
| Reproducible metrics | Saved measurement definition `human-claims-and-anchors:1`, raw counts, sample sizes and recomputation comparison. Unsupported/uncertain/partial judgments remain distinct. Missing measurements stay null; genuine zero values are displayed. |
| Operations | Inclusive UTC date selection translated to an exclusive end boundary, observed request/job latency with denominators, model/provider usage estimates, unknown usage counts, failures, review outcomes, throughput, daily activity and paginated request inspection. |
| Safe request logs | JSON request ID, method, route template, HTTP status and elapsed time; no request bodies, cookies or query strings. API migrations retain request loggers. |
| Recovery | Encrypted and checksummed logical database/storage/master-key bundles; maintenance-window requirement, full table inventory and a new empty restore target. SQLite and PostgreSQL supported. |
| Release configuration | Full backend/fixture-validation and frontend CI gates; independent PostgreSQL container gate; Vercel frontend configuration, explicit HTTPS backend requirement and 4 MB upload UI budget. |

Schema revision: `0009_measured_evaluations` (additive). Legacy evaluation values remain inspectable as historical records without a new provenance claim. The old placeholder evaluation runner is no longer exposed as a working live-quality measurement; its POST endpoint returns 410 and directs clients to the durable workflow. `eval/run_eval.py --dry-run` strictly validates illustrative fixtures and emits no fabricated accuracy/cost/latency.

## Metric interpretation and bounds

Fact accuracy is human-supported claims divided by an explicitly complete claim inventory. Unsupported-claim rate is independently counted unsupported claims divided by that inventory. Both require every case measured and no uncertain judgments. Citation coverage counts annotated claims with exact recorded output passages and matching recorded source anchors; location matching does not establish truth. Style adherence uses only explicitly human-assessed cases. The UI shows these definitions and denominators.

Operational cost sums saved usage at each request's saved pricing; it is an estimate, not a provider invoice. Unknown requests are counted and excluded from known cost/tokens. Job latency includes queueing and requires recorded finish times. Review outcomes are workflow results, not benchmark factual accuracy. Queries permit at most 366 days; summaries above 50,000 requests require a narrower range. Dataset creation supports 50 cases/100 claims per case; hosted requests must also fit the platform body limit. Detail pages return at most five cases per request.

## Automated verification evidence

The final container suites passed **459 PostgreSQL tests** and **456 SQLite tests / 3 PostgreSQL-only skips**. Production-profile generation/API restart, outage readiness, non-root image, shared-storage and container/database restart persistence checks also passed. Evidence is recorded in `.runtime/phase8-docker-verification-final.log` and `.runtime/docker-verification/report.json`. All tests use isolated databases and mock providers; the separate live acceptance is explicitly identified below.

- Native full regression checkpoint: 453 passed, 4 environment-specific skips. The final added checkpoint-resume and canonical-review cases passed in the expanded 12-test measurement/recovery suite.
- Targeted generator/reviewer/pipeline regression after canonical section alignment: 126 passed.
- Queue, lease renewal, measurement and migration targeted regression: 32 passed.
- Frontend: 36 transport/recovery/API tests passed; lint, TypeScript and the production build passed. Production `next start` returned HTTP 200; API readiness returned HTTP 200.
- Strict illustrative fixture validation: seven fixtures, no invalid source spans, all quality/cost/latency fields null.

New tests verify independent metric numerators and denominators, zero/null distinctions, idempotent admission, no provider calls during scoring, quote validation, changed-source failures, tenant/legacy ownership, viewer write denial, cancellation, checkpoint recovery, recorded timing/usage and safe structured logs. Encrypted recovery tests also authenticate against the restored instance, read drafts/saved versions/approvals/comments and export the exact version. A loaded SQLite lease renewal regression protects long provider requests against naive/aware datetime comparison errors.

## Browser acceptance

A separate synthetic SQLite database and fixture API were used; no fixture accounts, datasets, calls or benchmark results were inserted into the real workspace. The owner created a dataset through the browser, selected a saved version, inspected the source, annotated an exact claim and a style judgment, saved and scored the dataset, then inspected completed results and judgments. Stored metrics matched recomputation. The viewer could inspect results without create/score controls. A request-status filter changed the count from three requests to one failed request. Empty dataset/execution and unknown-usage states were visible. Desktop, 820×1180 tablet and 390×844 phone layouts were inspected; tables scroll within their containers and result cards stack on phone. Native labeled controls and visible keyboard focus were checked; this is not a formal accessibility audit.

Screenshots (synthetic acceptance data):
- `.runtime/phase8-ui/operations-desktop.png`
- `.runtime/phase8-ui/operations-tablet.png`
- `.runtime/phase8-ui/benchmark-desktop.png`
- `.runtime/phase8-ui/benchmark-phone.png`
- `.runtime/phase8-ui/benchmark-viewer-desktop.png`

The fixture API was stopped and the normal API/worker/frontend were restored. Normal startup evidence: `.runtime/phase8-startup-report.json`. No first-owner account was created for the real user; the setup form remains ready for their own credentials.

## Real workspace preservation and recovery

With no queued/running jobs, the normal API/worker were stopped and a cold database/storage snapshot was saved privately. The actual database was migrated, encrypted into a recovery bundle and restored into a separate new database and storage directory. Every application table count matched, including all **23 sources, 38 generations and 51 artifacts**. A separate preservation comparison confirmed all original columns across **30 business tables** and all **43 original storage files** remained unchanged (worker heartbeats and schema metadata excluded). Neither the original workspace nor the restored target was seeded with synthetic test users. Evidence: `.runtime/phase8-recovery/report.json` and `.runtime/phase8-recovery-check.log`.

The bundle includes private workspace content and its provider master key; it and its separate recovery key are excluded from git. These locally colocated verification files are not off-device disaster protection. Follow RECOVERY.md to retain copies independently. The supported logical bundle limit is 256 MiB and requires a stopped-writer maintenance window; environment/deployment configuration needs its own protected backup.

## Live-provider gate — still open

Live checks used only fictional Cedar Garden text, isolated SQLite databases and an explicit estimated USD 0.15 per-run ceiling. Provider: configured Gemini `gemini-3.1-flash-lite`. The first check exposed a SQLite heartbeat synchronization bug; it was corrected and covered by repeated-renewal regression. Another check exposed old executive specialist sections/hashtag detection; the specialist and planner now follow the canonical format sections and allow Markdown headings. Evidence validation was kept strict and prompts now explicitly require final-output claim excerpts.

An earlier correction request returned a temporarily-busy provider failure. After waiting for the full local regressions, a fresh bounded run completed all nine real provider calls, including regeneration and both rounds of style/fact/compliance review. Latest run: `133bb3d1-8b0d-4967-800a-6a3c35db5c77`. Source anchors matched 4/4, but three recorded claim strings were still not exact excerpts of the final output. The saved draft therefore remains failed/needs-review. Recorded usage was 15,566 tokens and estimated cost USD 0.03133; unknown charges from the earlier interrupted check are not asserted to be zero. The latest run did not pass live verified-output acceptance. Report: `.runtime/phase8-live-report.json`; repeatable bounded command: `python scripts/verify_live_release.py` (paid provider calls).

This demonstrates real calls, persisted drafts and honest failure handling; it is not proof of reliable production-quality generation. Do not remove the review/evidence failure to mark this gate complete. A fresh bounded run must produce exact references and pass all required checks; hosted acceptance follows once hosting is available.

## Deferred hosting and remaining release work

No Vercel project or public backend URL was supplied, and the user explicitly chose to deploy later. `frontend/vercel.json`, VERCEL_DEPLOYMENT.md and RECOVERY.md prepare the release. Public HTTPS backend/worker/database/storage hosting, Vercel environment variables/domain, hosted cookie/origin/upload/export acceptance and the successful live verified-output gate remain open. The actual user must complete first-owner setup with their own credentials. Local automated tests do not replace these hosted/user-owned steps.
