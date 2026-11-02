# TraceForm completion plan

Prepared: 30 October 2026

Progress: Phases 1–3 verified locally, including PostgreSQL Docker deployment checks.
Phase 4 is implemented and locally verified with automated and isolated browser tests;
real-provider acceptance remains pending because Gemini returned 503/504 errors.
See `docs/planning/feature-ledger.md` for evidence and supported boundaries. Phases 5–8 remain pending.

## Objective

Complete the previously discussed generation, evidence, editing, export, multi-source,
metrics, and team features. Each feature includes its API, persistence, usable interface,
failure handling, and functional verification. A visible control is complete only when
its intended action works against the real backend.

## Initial baseline and gaps (before implementation)

Implemented: a three-step creation flow, output-first workspace, source-text references,
review results, local drafts, Markdown/text downloads, stage events, provider checks,
bounded transient retries, retry of unsuccessful output types, and new-version creation.

The initial targeted validation passed 66 backend tests and TypeScript checks. Current
phase results are recorded in `docs/planning/feature-ledger.md`; these original gaps are historical.

Confirmed gaps from the code review:

- Settings is a placeholder.
- The evaluation endpoint supplies sample benchmark figures when no evaluation exists.
- Some backend quality/differentiation scores and older UI review/latency fallbacks are constants.
- Draft versions are browser-local rather than shared, durable records.
- Normal API dispatch launches an in-process background task; it does not survive API restarts.
- Frontend calls for some artifact actions need reconciliation with backend route contracts.
- Database migration infrastructure exists without a complete versioned migration history.
- The newly simplified workspace does not yet cover every older dashboard surface.

## Completion rules for every feature

1. Write its user scenario, supported inputs, permissions, and expected result.
2. Define and implement the API contract and persistence, including migrations.
3. Implement loading, empty, success, validation, permission, and failure states.
4. Give errors a useful next action while preserving the user's inputs and existing work.
5. Verify keyboard operation, focus, readable contrast, narrow screens, and long content.
6. Add meaningful backend and browser tests covering the scenario and its main failure paths.
7. Exercise the real workflow in the local app; isolate mock providers to explicit test/demo modes.
8. Record evidence, limitations, and completion status in the feature ledger.

## Phase 1 — Feature inventory, honest data, and UI foundations

### Functionality
- Inventory every route, page, action, output type, configuration option, and claimed capability.
- Map every frontend API call to a supported, authenticated backend endpoint.
- Remove fabricated benchmark records, invented review results, and constant quality/latency scores.
- Represent unavailable measurements as unavailable, rather than zero or a successful result.
- Separate demo fixtures from live data; identify demo mode visibly.
- Establish shared request/response contracts and validation.

### Interface
- Use consistent navigation, names, buttons, typography, forms, status labels, and spacing.
- Standardize empty states, errors, notifications, confirmation dialogs, and focus behavior.
- Apply the system to Outputs, Create, History, Evaluation, Settings, and older drawers/modals.
- Replace unsupported marketing claims with accurate capability descriptions.

### Acceptance
- Every visible action has a tested implementation or is removed from the live interface.
- Empty evaluation data never appears as a measured benchmark.
- Shared UI patterns pass keyboard and responsive checks.

## Phase 2 — Durable generation and usable configuration

Status: verified on the local SQLite deployment, 30 October 2026. API restart, worker
process interruption, duplicate requests, cancellation, provider settings and budget
reservations have recorded checks. PostgreSQL 15 Docker deployment verification passed
on 31 October 2026; see [feature ledger](feature-ledger.md) and [PostgreSQL deployment guide](../deployment/postgresql.md) for evidence and scope.

### Functionality
- Use a durable worker queue for normal dispatch; make local development setup repeatable.
- Track job ownership, heartbeats, stage attempts, cancellation, timeouts, and terminal outcomes.
- Recover interrupted jobs and make repeated dispatch/retry requests idempotent.
- Reuse a validated extraction when safe, with source/model/prompt versions recorded.
- Preserve successful outputs and retry only incomplete work.
- Track the model actually used, provider errors, token usage, and pricing versions.
- Define budget semantics, account for concurrent work, and disclose estimates or overruns.
- Add versioned migrations and verify updates preserve existing data.
- Implement server-backed provider/model settings, credential validation, and availability checks.
- Keep credentials server-side; return masked status rather than secrets.

### Interface
- Add a functional Settings page with clear connection status, model selection, and test/save feedback.
- Show real stage/output progress, recovery guidance, cancel, and retry controls.
- Explain when a fresh version or fresh budget will be created.
- Preserve the source and customization if a request fails.

### Acceptance
- A running job survives an API restart and recovers correctly after worker interruption.
- Duplicate requests do not create duplicate billed work or duplicate artifacts.
- Provider outages, invalid credentials, quota exhaustion, cancellation, and budget limits are tested.

## Phase 3 — Source library and controlled creation

Status: verified locally, 31 October 2026. Library upload/search/pagination/preview,
protected reversible removal, operator-private presets, four-step creation and all 13
format contracts are implemented and tested. Image OCR requires a server Tesseract
installation; this machine currently verifies its missing-engine error path. Format
checks validate structure; factual/style quality remains independently reviewed.

### Functionality
- Separate source management from creation while retaining quick reuse in the creation flow.
- Support validated uploads, extraction status, previews, search, pagination, and safe deletion rules.
- Make file-size, type, extraction, OCR, and truncation behavior explicit.
- Support persistent audience, tone, language, length, goal, section, and brand presets.
- Verify every advertised output type against its own schema and expected structure.

### Interface
- Provide a searchable source library with understandable filenames and previews.
- Keep creation short; show common formats first and advanced options on demand.
- Explain whether a format produces a document, an outline, or an actual media file.
- Provide an accessible review step summarizing the source, outputs, preferences, and budget.

### Acceptance
- New and saved sources work with every supported output type.
- Invalid, empty, oversized, encrypted, and poorly extracted documents receive actionable errors.
- A failed start can be retried without re-uploading the source.

## Phase 4 — Output quality, review, and source evidence

Status: implemented, 31 October 2026. Exact source anchoring, typed claim references,
calculation checks, source/content identities, bounded correction history, durable
unreviewed checkpoints, actionable findings, feedback and role-controlled exceptions
are implemented. Desktop/phone workflows and automated suites are verified. The live
Gemini acceptance run did not complete successfully due to provider 503/504 responses;
this gate remains open and is not represented as a verified output.

### Functionality
- Validate citations against actual source text and retain stable document/span identifiers.
- Distinguish source facts, derived calculations, recommendations, and unsupported statements.
- Ensure review badges reflect actual recorded checks and relevant policy gates.
- Retry correctable generation errors with explicit feedback; keep unresolved failures visible.
- Record coverage and limitations without presenting model confidence as certified accuracy.
- Support feedback and permission-controlled overrides with reason and audit history.

### Interface
- Connect generated claims to highlighted source passages in context.
- Show actionable reviewer findings beside the affected text.
- Clearly label unverified text, failed checks, overridden decisions, and missing evidence.
- Keep technical provenance available in collapsed details.

### Acceptance
- Tests cover altered numbers, invented entities/deadlines, unsupported claims, bad offsets,
  missing sources, conflicting statements, and instruction-like content inside source documents.
- Failed or overridden checks are never silently displayed as verified.

## Phase 5 — Durable editing, versions, and polished exports

Implementation and local verification are recorded in [Phase 5 verification](../verification/phase-5.md).
The live-provider acceptance gate remains pending; mocked checks are identified separately.

### Functionality
- Store drafts and immutable versions on the server, with recovery and conflict handling.
- Migrate browser-local drafts through an explicit import/recovery path.
- Add autosave, restore, comparisons, full-output regeneration, and section-level regeneration.
- Mark edited material as unreviewed and provide re-review for the actual saved version.
- Export Markdown, text, DOCX, PDF, and PPTX where appropriate to the output type.
- Include optional citations and provenance in exported files.
- Preserve formatting, Unicode, tables, headings, lists, pagination, and long content.

### Interface
- Keep Edit, Save status, Copy, Download, New version, and Review close to the content.
- Provide understandable version names, change comparisons, and restore feedback.
- Show export formats relevant to the current output and label original versus edited exports.
- Handle unsaved work and regeneration scope explicitly.

### Acceptance
- Drafts survive refresh, sign-out/re-entry, and use from another authorized session.
- Editing cannot retain the original version's verified badge without a new review.
- Downloaded files open in their target applications and pass rendered layout inspection.

## Phase 6 — Multiple-source synthesis

### Functionality
- Support named source collections and per-run selection of several versioned documents.
- Extract and cite evidence per document; deduplicate facts without losing attribution.
- Detect conflicts, record missing evidence, and expose user-selected resolution rules.
- Respect document permissions and sensitivity throughout generation, review, and export.

### Interface
- Provide a simple source picker with a visible selected-document list.
- Show conflicting claims with their source passages and a clear resolution choice.
- Allow references to be filtered by source document.

### Acceptance
- Contradictory figures/dates are exposed rather than silently merged.
- Every citation opens the correct document and version.
- Removed or inaccessible sources cannot leak into new runs or exports.

## Phase 7 — Teams, approvals, and audit history

Status: implemented and verified locally. Session authentication, workspace isolation,
role controls, invitations, version-bound approvals, comments and searchable activity
are implemented. Verification and initial-owner setup are documented in
[Phase 7 verification](../verification/phase-7.md). Docker verification passed on 2 November 2026. Hosted and live-provider acceptance remain open.

### Functionality
- Implement authenticated users, workspaces, invitations, and owner/editor/reviewer/viewer roles.
- Enforce workspace isolation on sources, runs, drafts, versions, downloads, and audit events.
- Add comments, assigned reviews, approval states, and immutable approval/version relationships.
- Record significant changes and permission-controlled overrides in an audit log.
- Add searchable/paginated history with working filters and direct links to exact versions.

### Interface
- Add workspace/member management and understandable role controls.
- Provide a review inbox, comment threads, approval actions, and activity history.
- Explain read-only states and denied actions without exposing another workspace's data.

### Acceptance
- Permission tests verify cross-workspace isolation for every resource and export route.
- Editing an approved output requires re-approval of the new version.
- Audit records identify actor, action, time, resource, and relevant version.

## Phase 8 — Evaluation, operations, and release verification

Status: implemented with local tests, browser and encrypted recovery evidence. See
[Phase 8 verification](../verification/phase-8.md). Vercel hosting is prepared and deferred
at the user's request; successful live verified-output acceptance remains an open release gate.

### Functionality
- Persist real evaluation datasets, executions, outcomes, sample sizes, and measurement versions.
- Calculate each metric from the evidence that supports it; do not infer one metric from another.
- Track observed latency, model-specific cost, provider failures, review outcomes, and throughput.
- Add operational logs, health checks, backup/restore, deployment configuration, and CI gates.
- Document local startup, worker requirements, migrations, configuration, and recovery procedures.

### Interface
- Display honest no-data states, date ranges, dataset sizes, and metric explanations.
- Make evaluation runs and their failures inspectable.
- Label historical/demo data and estimated costs explicitly.

### Acceptance
- Recomputed metrics match their saved evaluation results and sample sizes.
- Backups restore into a working environment with sources, drafts, versions, and audit records intact.
- Production build and startup succeed using documented configuration.

## Feature completion ledger

Maintain one row per feature with these fields:

| Field | Required content |
| --- | --- |
| Feature and scenario | The user action and expected outcome |
| Status | Planned / In progress / Blocked / Verified |
| API and persistence | Implemented routes, contracts, permissions, migrations |
| Interface | Screens, states, keyboard and responsive behavior |
| Automated evidence | Relevant unit, integration, contract, and browser tests |
| Manual evidence | Verified real workflow, screenshots, and export render checks |
| Limitations | Explicit remaining issues or supported boundaries |

## Final release gate

- Full backend suite passes; newly introduced failures are resolved.
- Frontend type checking, linting, and production build pass.
- Browser tests cover upload/reuse, creation, progress, failure/retry, cancellation, evidence,
  editing/autosave, versions, re-review, exports, history, settings, and permissions.
- The output-format matrix is verified with representative short, long, and malformed sources.
- Worker/API restart recovery and duplicate submission behavior pass.
- Desktop, tablet, phone, keyboard-only, long-content, empty, loading, and error states are checked.
- Real-provider smoke tests pass separately from deterministic mocked-provider tests.
- No fabricated production metrics, hidden fallback success states, or unsupported live controls remain.
- Each feature's ledger row contains evidence; incomplete items remain visible rather than being
  described as finished.

Implementation proceeds in phase order, completing API, persistence, interface, and verification
for each feature together. Later phases can depend on earlier foundations, but an unfinished
feature is not marked complete just because its screen exists.

## Phase 6 verification status

Implemented and verified locally. SQLite/PostgreSQL regressions, frontend checks and browser workflow passed. Docker container verification passed in the 2 November 2026 follow-up; real-provider acceptance remains pending. See [Phase 6 verification](../verification/phase-6.md).
