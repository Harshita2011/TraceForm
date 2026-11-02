# Phase 7 — Teams, approvals and audit history

Implemented and verified locally on **2 November 2026**. Hosted release acceptance remains a separate gate.

## First use

Open `http://localhost:3000/dashboard/team`. Create the first owner with your name, email, a password of at least 12 characters and an administrator installation key from the backend configuration. Migration creates no account or password. The owner claims the existing workspace with its preserved sources and outputs.

The normal app is running with migration `0008_team_workspaces`. API readiness and the independent worker health check passed. All original business rows are unchanged across every original column: 23 sources, 38 generations, 51 artifacts, one preset, existing provider configurations and histories. No test identities, memberships, comments or decisions were copied into the real database.

## Features and rules

| Feature | Implemented behavior |
| --- | --- |
| User authentication | Salted scrypt passwords, generic login errors, bounded per-process login throttle, hashed opaque session tokens, eight-hour expiry, logout revocation, HttpOnly/SameSite=Strict cookies; Secure cookies in production |
| Browser transport | Same-origin proxy, explicit cookies, origin checks, no installation key in client code, no response caching; initial setup requires an explicitly entered admin key |
| Workspaces | Membership-based selection, empty new workspaces, central tenant criteria for API reads/writes and independent worker execution; existing rows remain in `legacy` |
| Roles | Owner manages membership/invitations; editor creates and edits; reviewer comments and decides assigned reviews; viewer reads and downloads. Live membership/role lookup applies changes on the next request |
| Membership controls | Owner/editor/reviewer/viewer role controls, access removal, serialized last-owner protection including simultaneous demotions |
| Invitations | Email-bound one-time tokens stored as hashes, three-day expiry, revocation, existing-account password verification; shareable fragment links keep the token out of HTTP query logs. Delivery is manual |
| Shared and private work | Workspace sources, outputs, collections, presets and immutable versions are shared with members. Working drafts remain private to the user. All resources stay within their workspace |
| Assigned reviews | Review inbox with status and assignee filters, exact saved content, notes, approve / request-changes decisions, revision-checked concurrent decisions |
| Approval binding | Immutable decision rows reference the exact saved version and content hash. New edited versions begin unapproved. Human approvals and automated content checks have distinct UI states |
| Discussions | Version-scoped comments, root-thread replies, resolve/reopen controls, pagination and viewer read-only states |
| History and provenance | Searchable/paginated activity with actor/action filters, immutable actor/time/resource/version records, direct links to exact versions. Optional export provenance includes the saved version's human approval and decision identity |
| Installation settings | Original-workspace owners manage installation-wide providers. Provider secrets remain encrypted; other workspaces use the configured provider without permission to change installation settings |

The workspace boundary covers sources/text, generation status and actions, extracted knowledge, saved collections/presets, drafts, immutable versions, version tasks, comments, reviews, audit/evaluation/metrics feeds and downloads. Legacy integration keys remain scoped to the original workspace. Their existing operator rules remain compatible; team users use membership roles and sessions.

## Verification

| Evidence | Result |
| --- | --- |
| Full SQLite regression checkpoint | **439 passed, 4 skipped**: three PostgreSQL-only tests and the native PDF conversion dependency |
| Full PostgreSQL 18 regression checkpoint | **442 passed, 1 native PDF dependency skip** |
| Final expanded team and audit suite after recovery/isolation refinements | **16 passed on SQLite and 16 passed on PostgreSQL** |
| Frontend contract/recovery/proxy tests | **31 passed** |
| Frontend ESLint, TypeScript and production build | Passed |
| Production-profile PostgreSQL smoke | Repeatable migrations; API restart during generation; independent worker completion and health; duplicate submission; cancellation; encrypted credentials; five recorded local HTTP provider calls / 150 tokens |
| Data preservation | Original rows compared against the pre-migration SQLite backup; all original business columns and rows unchanged; no Phase 7 fixture rows in the actual DB |

The full regression checkpoints preceded the final stale-cookie recovery case, expanded route matrix and audit refinements. The final 16-case suite covers those changes on both databases; its results are recorded separately, not added to the full-suite totals.

The permission matrix exercises cross-workspace source and text reads, lists/metrics/history/evaluations, generation status/actions, private draft writes, shared version reads/restores/tasks, comments/decisions, collections/presets, and **MD/TXT/DOCX/PDF/PPTX exports for both original and saved-version targets**. Inaccessible resources return not-found responses without another workspace's content. Tests also cover session/invitation expiry, revoked access, role downgrades, last-owner concurrency, decision/audit immutability independent worker tenant inheritance, and a complete authenticated-workspace generation through provider checkpoints, extraction, review and artifact persistence.

Browser verification used an isolated SQLite database and synthetic owner/editor/reviewer/viewer accounts. It covered sign-in/out, exact-version review, approval, comment resolution, activity actor/action filters, owner role controls, invitation creation/revocation, fragment links, and switching to a genuinely empty separate workspace. Exact-version navigation opened the correct version with editing disabled for the reviewer. Phone 390×844 and tablet 820×1180 had no horizontal overflow; temporary viewport changes were reset.

Verification found and corrected canonical-slash handling in the new proxy, a SQLite timezone comparison in invitation admission, the last-owner race, stale-cookie setup recovery and inaccessible-run cancellation responses. The normal app and its independent worker were restored afterward.

## Evidence files

- `.runtime/phase7-sqlite-release.log` and `.runtime/phase7-postgres-final.log`
- `.runtime/phase7-teams-final-sqlite.log` and `.runtime/phase7-teams-final-postgres.log`
- `.runtime/phase7-postgres-smoke.json`
- `.runtime/phase7-preservation-before.json` and `.runtime/phase7-preservation.json`
- `frontend/.visual-check/phase7-approved-review.png`
- `frontend/.visual-check/phase7-filtered-activity.png`
- `frontend/.visual-check/phase7-team-desktop.png`, `phase7-team-phone.png`, `phase7-team-tablet.png`
- `frontend/.visual-check/phase7-separate-workspace.png`

These runtime artifacts are ignored by Git. The local first-owner setup must be completed by the user with their own credentials.

## Docker follow-up — 2 November 2026

The Docker blocker is cleared. The current image built successfully and the isolated
`traceform-pgverify` stack migrated to `0008_team_workspaces` on PostgreSQL 15.19.

| Container check | Result |
| --- | --- |
| Full PostgreSQL suite | **446 passed** |
| Full SQLite suite | **443 passed, 3 PostgreSQL-only tests skipped** |
| Production generation and API restart | Passed with local HTTP provider fixtures |
| Database-outage readiness | Correct HTTP 503 |
| PostgreSQL/container restart and shared-storage persistence | Passed |
| API, worker and PostgreSQL health | Healthy after restart |
| Non-root runtime; local env/database excluded from image | Passed |

Investigation of an initial SQLite cancellation timeout exposed a heartbeat monitor
failure path that could leave execution running without cancellation checks. The worker
now stops execution when the monitor fails and uses the existing durable recovery path.
A deterministic fault-injection test covers this behavior. All 22 durable-worker tests
passed natively, followed by the complete container suites above after rebuilding.
The cancellation test's lease and assertions were retained.

Evidence: `.runtime/docker-verification/report.json`, `pytest-postgres.log`,
`pytest-sqlite.log`, `production-smoke.log`, and `.runtime/phase7-docker-build.log`.
The test API uses loopback port 18000 and separate databases/storage from the normal app.
The native worker had no active jobs and was restarted to apply the heartbeat fix;
its health check passed and the normal API readiness endpoint returned HTTP 200.

## Remaining release gates

Docker container verification is now complete locally. Earlier real-provider end-to-end acceptance also remains pending; this phase's provider verification used local deterministic HTTP fixtures and made no paid provider calls. Production deployment requires HTTPS, exact frontend origins and shared edge rate limits across API replicas. Phase 8 evaluation/operations/release verification remains next.
