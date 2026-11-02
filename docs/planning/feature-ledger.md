# TraceForm feature ledger

Current status: Phase 8 is implemented with local automated/browser and encrypted recovery evidence.
See [Phase 8 verification](../verification/phase-8.md) for measured-result definitions and current release gates.
Vercel hosting is prepared and explicitly deferred; live verified-output acceptance remains open.

Phases 1–3 verified locally, 31 October 2026. This ledger separates working features from
later-phase capabilities; passing checks for a phase do not mark the whole product complete.
Phase 4 is implemented with local automated/browser evidence below; its live-provider
acceptance gate remains open due to Gemini 503/504 responses.

## Current screens and actions

| Surface | Implemented behavior | Remaining work |
| --- | --- | --- |
| My outputs | Read real runs, search/filter recent work, select output, inspect stage events, retry failed outputs, create new version; current assurance drives badges | Shared versions: Phase 5; team permissions: Phase 7 |
| Create output | Upload/reuse source, paginated picker, formats, saved presets, audience/tone/language/detail/goal/sections/brand, explicit review step and budget | Deeper evidence/review and richer exports: Phases 4–5 |
| Source library | Validated uploads, extracted-text preview, filename search, sensitivity filter, pagination, trash/restore for unused sources; linked sources protected | OCR requires Tesseract; permanent purge/storage lifecycle: later operations work |
| Personal presets | Server persistence, apply/create/update/delete, operator ownership and revision conflicts; source/privacy/budget excluded | Team presets and workspace administration: Phase 7 |
| Output workspace | Exact source-context highlights, actionable findings, typed references, required/advisory checks, correction history, version-bound feedback and compliance exceptions; copy and Markdown/text downloads | Server autosave, version comparisons, re-review and richer exports: Phase 5 |
| Draft versions | Explicitly browser-local; edited drafts are labeled unreviewed | Shared durable draft storage: Phase 5 |
| Run history | Actual source filenames and sensitivity, real lifecycle filters, sorting, direct run links, loading/errors | Server pagination and audit activity UI: Phase 7; current view is explicitly limited to 200 recent runs |
| Evaluation | Versioned human-adjudicated datasets, durable scoring, exact-version inspection/recomputation, UTC operations and request filters | Live verified-output acceptance and deferred hosted checks remain open; see Phase 8 |
| Settings | Editable Gemini/Anthropic configuration, model discovery, encrypted keys, connection test, pricing revision and worker status | Per-user workspace administration: Phase 7 |
| Older artifact panels | No fabricated reviewer outcomes or default quality scores; artifact-ID contracts supported | Consolidation into the main output workspace; full review/version workflows: Phases 4–5 |
| Command palette | Working page navigation and create action | Global resource search: later source/history work; removed action that falsely claimed to rerun work |
| Marketing | Capabilities instead of fabricated benchmark counters/testimonials; example traces/logs explicitly labeled | Update capability descriptions as later phases ship |
| Demo mode | Visible banner; sample reads/mutations isolated from live mutation routes | Expand simulated workflows only when explicitly supported |

## Frontend → API contract inventory

All workspace resource routes below require the configured operator API key. The liveness
endpoint is intentionally public. Future workspace/user authorization belongs to Phase 7.

| Action | Endpoint |
| --- | --- |
| Upload / list sources | `POST /api/v1/sources`, `GET /api/v1/sources/` |
| Read source evidence | `GET /api/v1/sources/{id}/text` |
| Create / list / read generations | `POST /api/v1/generations/`, `GET /api/v1/generations/`, `GET /api/v1/generations/{id}` |
| Read recorded stages | `GET /api/v1/generations/{id}/status` |
| Retry unsuccessful outputs | `POST /api/v1/generations/{id}/retry` |
| New version of one output | `POST /api/v1/generations/{id}/regenerate?output_type=...` |
| Read artifact | `GET /api/v1/artifacts/{id}`; canonical generation/type route also remains supported |
| Save feedback | `POST /api/v1/artifacts/{id}/feedback`, body `{rating, comment}` |
| Justify compliance override | `POST /api/v1/artifacts/{id}/compliance-override`, body `{reason}`; source sensitivity is unchanged |
| Run history | `GET /api/v1/generations/history/list` |
| Operational counts | `GET /api/v1/metrics` |
| Recorded evaluation / history | `GET /api/v1/evaluations/latest`, `GET /api/v1/evaluations/history` |
| Provider test | `GET /api/v1/healthz/provider` |
| Recorded audit entries | `GET /api/v1/audit/trail`; dedicated activity UI is pending |
| Liveness | `GET /api/v1/healthz` |

Legacy typed rerun routes now create a separate durable generation with a fresh budget.
The evaluation-run API remains a backend capability; evaluation monitoring and approval UI are later work.
Removed unused frontend wrappers that called nonexistent source-detail and generation-rerun routes.

## Output format inventory

Current formats: executive summary, leadership briefing, research report, presentation outline,
LinkedIn post, press release, strategy memo, advisory memo, policy memo, newsletter, X thread,
infographic outline, and video script. The creation UI describes outlines/scripts as such;
it does not promise generated images or video. The Phase 3 scenario matrix now verifies admission for new/saved sources, generator contracts
and required structure for all 13 formats. Rich export verification remains Phase 5.

## Honest-data changes

- Existing evaluation rows have no recorded live/demo provenance and are labeled historical/unverified; they are not certified as live benchmarks.
- No evaluation record returns `null`, not an invented 500-sample benchmark.
- Citation coverage and hallucination rate remain unmeasured when not separately persisted.
- A measured zero remains zero; it is not replaced with a favorable fallback.
- Operational pass rates are not labeled fact accuracy or certified benchmark results.
- Unknown averages/rates on empty data are `null`; observed counts/totals may correctly be zero.
- Reviewer results are never filled in as passed when absent; missing latency/quality measurements
  are not assigned constants.
- Differentiation is exposed only with the marker written by actual batch measurement.
- Demo evaluation executions do not persist live benchmark rows and use separate report names.
- Connection/model editing is now server-backed. Shared drafts remain a later phase.

## Verification

Automated checks: full backend pytest suite, frontend API contract tests (`npm test`), TypeScript,
full lint and Webpack production build. Browser checks cover evaluation no-data/error presentation,
history links/filters, settings connection feedback, and responsive layout. Screenshots are saved
under `frontend/.visual-check/` as verification artifacts, not application source.

Phases 2–4 verification is recorded below. Phase 4's real-provider acceptance remains
open; shared editing and richer exports belong to Phase 5.

### Phase 1 recorded results

- Full backend suite: **274 passed**.
- Frontend contract suite: **6 passed**.
- Full frontend lint: passed without errors or warnings.
- TypeScript and the standard `npm run build`: passed with Webpack.
- Live browser checks: historical evaluation provenance/unmeasured fields; combined history
  search/status filters; provider connection test returned Available; Settings and History
  at a 390-pixel viewport had no page-level horizontal overflow.
- UI preview: `frontend/.visual-check/phase1-settings.jpg`.
- Later phases remain pending; no claim is made that durable workers, shared drafts,
  all document exports, or team permissions are already complete.


## Phase 2 — Verified local behavior

| Feature/scenario | API and persistence | Interface and evidence |
| --- | --- | --- |
| Durable execution | Generation, queue entry and request key commit together; separate `python -m orchestrator.worker` process | Worker online/offline status, saved queue message, progress and attempts |
| Ownership and recovery | CAS leases, heartbeats, fencing, timeout, recovery limit and pipeline fingerprint | Saved calls replay without new usage; unknown in-flight outcomes require explicit retry |
| Duplicate submissions | Scoped Idempotency-Key and payload digest; per-job call fingerprint | Create/retry/version actions retain keys after a failed HTTP request; same key returns original run |
| Cancellation | `POST /generations/{id}/cancel`; queued cancellation is immediate, running cancellation reaches the worker heartbeat | Cancel button, terminal Cancelled label, preserved outputs and billing guidance; desktop and mobile checks |
| Resume/retry | Passed output IDs preserved; unfinished checkpoints update without duplicates; extraction reuse validates source/model/provider/prompt/schema/spans | Retry requests only remaining outputs, uses current provider and a fresh budget; original run stays intact |
| Usage and budgets | Atomic per-call reservations, saved provider/model/pricing version and response/usage/error records | Used/reserved/limit, incomplete-usage and overrun disclosure; technical provenance collapsed by default |
| Provider settings | GET/PUT `/settings/provider`, POST `/settings/provider/test`, POST `/settings/provider/models`; admin writes and revision CAS | Provider/model picker or manual ID, key replacement/removal, rates, test/save feedback and read-only permission state |
| Credential protection | Fernet-encrypted immutable snapshots; active settings pointer; production master key and operator authentication required | Only key-configured status is returned; credential-bearing validation input is never echoed |
| Schema/setup | Frozen additive migration history; existing schema adoption and repeatable upgrades | Local setup in `docs/development/local-development.md`; hidden Windows launcher and independent Docker worker |

### Recorded checks

- Final complete backend suite: **295 passed** (including 21 new durable-generation/settings tests).
- Frontend transport contracts: **9 passed**; full lint and production Webpack build passed. The build includes TypeScript checking.
- Tests cover concurrent claims, concurrent budget reservations, stale-owner fencing, saved-call replay without double usage, unknown-call recovery, timeout, running/queued cancellation, extraction invalidation, output preservation, encrypted settings, admin restrictions, revision conflicts, unknown usage and migrations.
- A subprocess test kills a worker after a provider response is committed, starts a new worker, and confirms one provider invocation, one artifact and 30 tokens recorded once across two worker attempts.
- Live Gemini smoke test used only the invented `Phase2_Synthetic_Verification.txt` garden fixture. Run `ff357967-0089-4937-a98a-c855afb62bc5` completed across an API process restart: one output passed, five calls succeeded, 7,317 tokens, estimated USD 0.01576125 at its saved fallback pricing, one worker attempt and zero remaining reservation. Duplicate HTTP submission returned the same run ID.
- Live Settings: connection test succeeded, 46 provider models loaded, existing configuration saved as revision 2 without exposing the key. A later slow availability check exposed the earlier 20-second timeout; it now allows the configured provider request window, and live admission succeeded afterward.
- Live queued cancellation: `49dfe0c4-a2e5-483d-bea0-e67b6d4161e9` became Cancelled through the UI while the worker was stopped, with zero generation calls dispatched. Queue was rechecked empty before restoring the worker.
- Settings and job controls were checked at 390 pixels: no page-level horizontal overflow (content width 384, viewport 390). Model/test/save controls have associated labels; native inputs and buttons remain keyboard accessible.
- Screenshots: `frontend/.visual-check/phase2-settings.jpg`, `phase2-settings-mobile.jpg`, `phase2-cancel-mobile.jpg`, and `phase2-generation.jpg`.
- The existing local database was backed up before migration under `traceform/storage_data/backups/before-phase2-20261030-230929.db`; original records were retained.

### Supported boundaries

This phase is verified on local SQLite. PostgreSQL enum/advisory-lock migrations and Docker configuration are implemented, but a PostgreSQL/container deployment was not available for a live check; that remains an explicit release verification task. Legacy pre-queue jobs are historical and never dispatched automatically.

Provider billing is external: a crash/cancel can leave a submitted request's outcome or charge unknown. Such requests are not silently repeated. Reservations and configurable rates are admission estimates, not an invoice or a guaranteed absolute spending cap. Unknown usage retains reservations, and the UI discloses missing totals/overruns. Provider availability can change after a successful test.

At Phase 2 completion, broader source validation and presets remained pending; Phase 3 results are recorded below. Deeper evidence, shared drafts, rich exports, multi-source work, team authorization and operational evaluation remain Phases 4–8.


## Phase 3 — Source library, presets and format contracts

Verified locally on 31 October 2026.

| Feature/scenario | Implementation | Verification |
| --- | --- | --- |
| Source management | Separate `/dashboard/library`; filename search, sensitivity filter, 12-item pages, text preview and direct reuse | API pagination/search/preview tests; live upload/search/preview/reuse on desktop and phone |
| Honest extraction | Reading/Ready/error states; metadata records filename, extraction method and truncation; reference-only videos cannot generate | Markdown acceptance fixed; binary/empty/corrupt/oversize files, encrypted/scanned PDFs, DOCX tables, low/unknown OCR and explicit truncation tested |
| Safe removal | Unused sources move to reversible trash; stored file retained; restore available; any saved generation blocks removal | Live trash/restore before generation; linked-source protection verified afterward; admission serializes with removal |
| Durable presets | Authenticated operator-private CRUD, revision checks; formats/audience/tone/language/detail/goal/sections/brand/style persist | Backend round trip, ownership, conflict and deletion tests; UI save/reload/apply verified |
| Controlled creation | Paginated quick picker and library reuse; upload/extraction before continuing; four-step review; preference/source preservation on failed start | Live preset restored all preferences after reload; source/privacy/budget stayed separate; failed provider admission reused one saved source in tests |
| Format contracts | Typed JSON envelope plus versioned required headings for every advertised format; additional sections checked; missing/empty/placeholder sections cannot pass | All 13 formats tested for new/saved-source admission, valid generator responses, invalid section structure and required prompt instructions |
| Publication gate | A failed structural check prevents a Passed artifact even when model reviewers report success | Explicit pipeline regression test; review pane displays recorded Format check and missing-section details |
| Migration | `0004_source_library` adds source metadata and presets without dropping existing data | Fresh/adopted-schema tests, repeated upgrades; live backup made first and all original 21 source IDs retained |

### Recorded results

- Final complete backend suite: **357 passed**, including **62 Phase 3 tests**.
- Frontend API contract suite: **12 passed**. Full lint and production Webpack build passed; build includes TypeScript checking.
- Desktop and 390-pixel mobile browser checks covered library search/preview, upload, reversible trash/restore, protected removal, preset persistence/application, format selection and review. Library and review pages measured 384-pixel content width in the 390-pixel viewport, without page-level horizontal overflow.
- Creation step changes move keyboard focus to the new heading. Inputs remain labeled, disclosure controls are native, and source/file switching is disabled during an upload to prevent stale selection races.
- Live fixture: `Phase3_Garden_Verification.md`, source `a79b5fe9-f60e-4ead-ae0c-61640d03a974`. Contains only invented, non-sensitive garden facts. Uploaded through the actual UI as Markdown, previewed, trashed, restored and reused without re-upload.
- Live preset: **Garden leadership**. Recovered its two formats and all writing preferences after reload; the budget correctly returned to the independent creation default until changed explicitly.
- Live run `5dd1b8d7-4cb5-4dd7-8c7b-eecf8f78ea55`: executive summary plus presentation outline, additional `Volunteer next steps` section, USD 0.30 admission limit. Both format checks passed. Presentation passed review; summary remained failed/unverified because fact review caught a model-added procurement deadline and style review caught unlabeled proposals. This is not reported as two verified outputs.
- That run recorded **19,976 tokens**, estimated **USD 0.04123375** at its saved pricing, with no active queue work remaining. Existing outputs and source evidence were preserved.
- Before migration: `traceform/storage_data/backups/before-phase3-20261031-002908.db`.
- Browser artifacts: `frontend/.visual-check/phase3-library.jpg`, `phase3-library-mobile.jpg`, `phase3-review.jpg`, `phase3-review-mobile.jpg`.

### Boundaries

PDF/DOCX/TXT/Markdown workflows are verified locally. Image OCR code has successful-provider, confidence-failure and missing-engine tests, but **Tesseract is not installed on this machine's PATH**; the live UI states that dependency and returns actionable errors. Scanned PDFs do not receive automatic OCR. Upload extraction is synchronous, not a separate durable extraction queue. Trashing retains raw files and does not permanently purge data.

Formats are written deliverables; presentation/infographic outputs are outlines and video output is a script. Structural validity does not certify facts, fulfill every style request, create media, or prove rich exports. PostgreSQL Docker deployment verification is recorded below. Phase 4 evidence/review behavior is implemented with its remaining acceptance gate recorded below; Phases 5–8 cover shared editing, exports, multi-source, team access and operations.

## PostgreSQL deployment verification — 31 October 2026

Verified in an isolated Docker Compose project, `traceform-pgverify`, using
`postgres:15-alpine` and the built Python 3.11 application image. Existing development
data was not migrated or reset. Test databases use dedicated `traceform_test_*` names.

| Scenario | Recorded evidence |
| --- | --- |
| Real PostgreSQL backend suite | **362 passed**; fresh/concurrent/repeated migrations, legacy data preservation, cancellation enum, source library, presets, all format contracts, durable dispatch and budget accounting |
| SQLite regression suite in the same image | **359 passed, 3 PostgreSQL-only tests skipped** |
| Production startup | One-shot migration exits successfully before API/worker startup; all three long-running services healthy |
| Generation across API restart | Independent API/worker processes inside the built image; local HTTP mock provider; worker completes one Passed artifact while API restarts; duplicate submission returns the original run |
| Persisted workflow | Source and preset retained; linked source removal blocked; second generation cancelled; encrypted provider credential and five recorded calls/150 tokens checked |
| Database outage and restart | Readiness returns 503 while PostgreSQL is stopped; services recover; completed/cancelled runs, source and preset survive PostgreSQL container restart |
| Shared file storage | A synthetic file written by the API container remains readable by the worker after restart |
| Image runtime | UID 10001, Tesseract 5.5.0 installed; local `.env` and SQLite database excluded |

The verification found and fixed PostgreSQL's unsupported two-argument rounding of
floating-point budget values by casting through Numeric while retaining atomic
increments. The container test also found a missing ReportLab dependency, now declared.
The Dockerfile uses requirements installation and a non-root runtime; Compose requires
deployment credentials and provides explicit migration/readiness/worker health checks.

Evidence: `.runtime/docker-verification/report.json`, `pytest-postgres.log`,
`pytest-sqlite.log`, `production-smoke-report.json`, `readiness-outage.log` and `restart.log`.
Repeatable commands are in [PostgreSQL deployment guide](../deployment/postgresql.md); scripts are
`scripts/verify_docker.py` and `scripts/verify_postgres.py`. A dedicated GitHub Actions
workflow was added; its hosted run has not been executed from this workspace.

The generation smoke uses synthetic input and a local mock provider, with no external
AI calls or charges. This verifies the backend deployment, not a hosted frontend,
load capacity, disaster recovery, or additional PostgreSQL versions.

## Phase 4 — evidence, review and controlled decisions

Implemented and locally verified on 31 October 2026. **Live-provider acceptance is
still pending**: the configured Gemini model returned 503 high-demand / 504 deadline
errors during the synthetic live checks. This phase is not described as fully signed off.

| Scenario | Implementation and evidence |
| --- | --- |
| Exact source identity | Document IDs, SHA-256 source/content versions, stable passage IDs and Unicode character ranges; no arbitrary first-substring fallback |
| Analyst anchoring | Exact offsets or a uniquely located verbatim quote; original model offsets and correction method retained; absent/ambiguous quotes rejected |
| Claim kinds | Source facts, explicitly labeled proposals, cited exact-decimal calculations and unsupported statements; translated labels remain visible in the requested language |
| Honest reference status | Anchor matching is separate from semantic support; altered numbers/dates/percentages fail even when the cited quote exists; counts are never labeled factual accuracy |
| Publication and correction | Style/fact/compliance/format/evidence gates; specialist heuristics explicitly advisory; one correction with failure feedback and inspectable attempt/content history |
| Review outages | Generated content checkpointed before provider review as unreviewed; corrected checkpoints retain their ID; stale workers cannot overwrite them |
| Feedback | Actual artifact/content identity, stale-version checks, attributed append-only audit events; no fixed invented artifact version |
| Compliance decisions | Reviewer/admin authorization on both route forms, meaningful reason, failed-compliance prerequisite and content binding; exceptions retain failed checks and source sensitivity |
| Usable evidence UI | Findings locate affected text; source passages highlight exact Unicode ranges; claim categories, calculation inputs/result, checks, correction history, provenance and recent decisions are inspectable |
| Draft safety and errors | Edited drafts are visibly unreviewed, original-version decisions disabled; failed saves retain input and offer a retry; keyboard focus moves to opened evidence and affected text |
| Additive migration | `0005_review_evidence` binds decisions to content; snapshot comparison confirmed all 22 original sources, 35 runs, 50 artifacts, one preset and two provider configurations unchanged |

### Recorded results

- Full backend suite in the final Docker image: **407 passed on PostgreSQL 15.19**;
  **404 passed on SQLite, 3 PostgreSQL-only tests skipped**. Includes **45 Phase 4 tests**.
- Frontend contract suite: **16 passed**. Full lint, TypeScript and production Webpack build passed.
- Production-profile local HTTP mock: repeatable migrations, separate worker/API execution,
  API restart during generation, idempotency, cancellation, encrypted credentials and usage
  recording passed. Database outage readiness and container persistence are recorded in
  `.runtime/docker-verification/report.json`.
- Isolated desktop (1440×1000) and phone (390×844) browser workflows covered matched
  facts/calculations/proposals, numeric findings, exact source and affected-text highlights,
  feedback, exception acknowledgment, retained failed badges, history after reload, keyboard
  access, local-edit safety and offline-save retry. The phone page measured 384 pixels in
  a 390-pixel viewport. Fixtures were in `.runtime/phase4-ui.db`, not the normal database.
- Screenshots: `frontend/.visual-check/phase4-findings-desktop.png`,
  `phase4-decisions-mobile.png`, `phase4-feedback-error-mobile.png`.
- Normal API, worker and frontend restored. The 22 original source IDs and original rows
  were preserved; one fictional `Phase4_Community_Garden.md` source was added for the
  capped provider checks. No fixture reviews were inserted into the normal database.

### Remaining acceptance gate and boundaries

The three real-provider runs failed: an initial extraction-offset error exposed the
need for unique-quote anchoring; subsequent runs encountered Gemini 504 review timeout
and 503 high demand. Known estimated usage was 17,306 tokens / USD 0.03887875; one failed
review request had no recorded usage. This is not asserted as a final provider bill.
No failed output was certified. Successful live-provider acceptance must be rerun when
the service is available.

Anchor checks do not prove that every output claim is covered or semantically correct.
Model reviews can miss errors. Rounded calculations/unit conversions, shared editing,
re-review of saved edits, team workspaces/approvals and richer exports are outside this
phase. See [Phase 4 verification](../verification/phase-4.md) for rules, evidence and the remaining gate. Phase 5 is
recorded below; Phases 6–8 remain pending.

## Phase 5 — durable editing, versions and exports

Implemented and locally verified on 31 October 2026. Successful live-provider
acceptance is still pending; synthetic HTTP-provider tests are explicitly separate.

| Feature and scenario | Status and evidence |
| --- | --- |
| Server drafts and autosave | Verified: serialized saves, revision checks, retry idempotency and private operator ownership; two real browser tabs exercised a conflict |
| Recovery and import | Verified: separate recovery copies per editor; a save in one tab cannot remove another copy; damaged storage does not hide valid legacy copies; explicit preview/import preserves the server draft |
| Immutable versions | Verified: named snapshots, paginated history, reopen, compare and restore; the prior differing draft is backed up before restore |
| Review saved edits | Verified with local HTTP mock: actual saved content is remapped and reviewed; no inherited original pass; style/fact/compliance/evidence/format results bind to content, source, sensitivity and policy |
| Full and section regeneration | Verified with deterministic providers: durable independent tasks, fresh explicit budgets, cancellation and original preservation; section boundaries are checked and regenerated copies start unreviewed |
| Portable exports | Verified: MD/TXT/DOCX/PDF; editable PPTX for presentation outlines; revision/hash checks, review labels, optional references/provenance, Unicode and long content preservation |
| Rendered layouts | Verified in LibreOffice: four document pages and thirteen slide pages inspected; Word title styling and PowerPoint footer overflow corrected; document skill renderer also completed |
| Feature UI | Verified: separate original/draft/version views, save states, conflict recovery, version comparison, scoped AI controls and relevant export formats; desktop, phone and tablet checks; browser DOCX/PDF/PPTX downloads |
| Data and deployment | Verified: additive `0006_artifact_versions`; all existing business rows unchanged; isolated fixtures; normal SQLite API/worker/frontend restored |

Full Docker regression checkpoint: **423 PostgreSQL tests passed**, **420 SQLite tests passed
with 3 PostgreSQL-only cases skipped**. Frontend: **22 tests passed**, lint, TypeScript
and production build passed. Production API restart, cancellation/idempotency, database
outage readiness and container persistence checks passed.
After the last export emphasis correction, the complete **17-case Phase 5 suite** passed
again in the container. The additional case is recorded separately from the full-suite counts.

See [Phase 5 verification](../verification/phase-5.md) for workflow rules, exact artifacts,
export dependencies and remaining acceptance boundaries. Operator-private editing uses
the current API-key identity; team authentication/workspace isolation remains Phase 7.

## Phase 6 — implemented and verified locally

| Feature | Evidence and status |
| --- | --- |
| Source collections | Private named collections; revision-checked updates; archive/restore; browser save and API tests passed |
| Multi-source creation | 2–8 separately extracted versioned documents; 200,000-character limit; explicit analysis budget; durable cancellation/idempotency; analysis reopen |
| Conflicts and attribution | Duplicate support retained; numerical and semantic conflict register; preserve/omit/prefer choices; exact passages; blocking checks |
| Evidence and exports | Source filtering and exact version checks; complete provenance; saved-version reviews and cloned runs retain snapshots; secondary-source changes block access |
| UI | Combined picker integrated into creation flow; visible selection, strictest sensitivity, decisions and separate budgets; desktop/phone/tablet checked |
| Verification | SQLite 430 passed / 4 skipped; PostgreSQL 433 passed / 1 skipped; frontend 25 passed; lint/types/build passed; PostgreSQL production restart smoke passed |
| Deployment boundary | Normal SQLite app migrated and restored with existing business rows unchanged. Docker follow-up passed on 2 November 2026; live-provider acceptance pending |

See [Phase 6 verification](../verification/phase-6.md) for limits, evidence, the test-isolation incident and remaining release gates. Team/document ACLs remain Phase 7; source access uses the current shared API-key library.

## Phase 7 — verified locally

| Feature | Current status |
| --- | --- |
| Authentication and workspaces | Session-based users, central workspace isolation, workspace switching and additive legacy-data migration verified |
| Members and invitations | Owner/editor/reviewer/viewer controls; one-time email-bound invitation links; expiry/revocation and last-owner concurrency verified |
| Team reviews | Assigned inbox, immutable version/hash decisions, fresh approval for edited versions, comments/replies/resolve controls verified |
| Audit and history | Actor/action search, pagination, exact-version links, immutable events and permission-controlled overrides verified |
| Feature UI | Owner management, reviewer inbox, clear read-only states, desktop/phone/tablet and empty-workspace checks passed |
| Verification | Full checkpoints: 439 SQLite / 442 PostgreSQL passed, environment-specific skips documented; final expanded team/audit suite 16 passed on each; frontend 31 tests plus lint/types/build passed |
| Data and startup | Existing business records preserved; normal API/worker/frontend restored. User completes first-owner setup with their own credentials |

See [Phase 7 verification](../verification/phase-7.md). Docker/container verification passed on 2 November 2026; earlier live-provider acceptance remains pending. Phase 8 covers evaluation, operations and release verification.

Docker follow-up: current image **446 PostgreSQL tests passed**, **443 SQLite tests passed / 3 PostgreSQL-only skips**. Production restart, outage readiness, non-root runtime, and container/storage persistence checks passed. A heartbeat-error recovery issue found during verification was fixed and covered by a new fault-injection test. See [Phase 7 verification](../verification/phase-7.md).


## Phase 8 — evaluation, operations and release preparation

| Feature | Status and evidence |
| --- | --- |
| Curated benchmark datasets | Immutable exact-version snapshots, human claim/style judgments, source-quote validation and provenance; owner/editor curation and workspace/legacy ownership checked |
| Durable scoring | Request idempotency, per-case checkpoints, cancellation, resume after interruption, failed-source inspection and saved-result recomputation checked without provider calls |
| Measured dashboard | Separate operations/benchmark tabs, UTC dates, known/unknown cost, actual timing samples, failures, request filters/history, case/result inspection and honest empty states; desktop/tablet/phone and viewer UI checked |
| Operational logging | Structured request correlation excludes bodies/cookies/queries; migration logger preservation checked |
| Backup/restore | Encrypted complete database/storage/master-key bundles; real local workspace restored separately with matching table counts; restored synthetic instance login/draft/version/approval/comment/export APIs checked |
| CI and Vercel preparation | Full backend/frontend gates, PostgreSQL Compose workflow, Vercel root/env/proxy/upload configuration and documented recovery/deployment steps prepared |
| Local runtime | Schema 0009; original 23 sources, 38 runs and 51 outputs preserved; API/worker and production frontend restarted |
| Remaining release gates | Live provider calls complete, but generated claim excerpt failures still block verified-output acceptance. Vercel/public backend deployment explicitly deferred. Real first-owner account remains for user setup |

See [Phase 8 verification](../verification/phase-8.md), [recovery guide](../deployment/recovery.md), and [Vercel deployment guide](../deployment/vercel.md).

Phase 8 final container regression: **459 PostgreSQL tests passed; 456 SQLite tests passed / 3 PostgreSQL-only skips**. Frontend: 36 tests, lint, TypeScript and production build passed.

Phase 8 production-profile Docker generation/restart, outage-readiness and container/storage persistence smoke checks passed.
