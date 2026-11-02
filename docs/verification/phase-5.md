# Phase 5 — editing, versions and exports

Implemented on 31 October 2026. Local verification is recorded below. Live-provider
acceptance remains a separate pending gate: Phase 4's Gemini 503/504 failures have
not been replaced by a successful live run. Phase 5 verification uses synthetic
documents and a local HTTP mock provider; it makes no external AI calls.

## Working behavior

- Original generated artifacts remain unchanged. Each operator gets a separate server
  draft with a revision number and immutable named versions.
- Draft changes autosave after an 850 ms pause. Saves are serialized, retry keys survive
  lost responses, and stale revisions return a conflict instead of replacing newer work.
- Every editor keeps its own browser recovery copy. Acknowledging one tab cannot erase
  another tab's unsaved copy. Valid recovery and legacy browser drafts can be previewed
  and explicitly imported without replacing the server draft.
- Restoring a version writes a draft and first saves the previous differing server draft
  as an immutable recovery version. Versions can be reopened, paginated and compared.
- Mutable drafts and new versions are unreviewed. Re-review evaluates the actual saved
  text, remaps its evidence and runs style, fact, compliance, evidence and format checks.
  Review evidence binds to content, source, sensitivity and the current review implementation.
- Full regeneration creates a new unreviewed version. Section regeneration includes the
  selected heading's subsections, preserves text outside that section, and rejects stale
  section IDs or replacement headings that would escape the selected scope.
- AI actions use the durable leased worker, immutable provider configuration, call ledger,
  budget reservations, cancellation and fresh explicit budgets. They continue after the
  page closes. An interrupted/failed call is not silently repeated as a paid retry.
- Revision jobs stay out of the main generation/history feed. Their usage is included in
  total usage/cost; averages for original generations use original generation costs.

The interface separates **Original**, **Working draft** and **Saved versions**, shows
save/conflict status next to the content, and offers scoped AI actions and export options.
Saved-version evidence cannot submit a decision against the original artifact. Original
review results and human decisions remain available in the Original view.

## Export contract

Markdown, TXT, DOCX and PDF are available for written outputs. Presentation outlines also
offer editable PPTX. Exports identify their selected target and review state; references
and source/version provenance are optional. Draft export checks the saved revision and
content hash. A stale request is rejected rather than exporting different content.

DOCX/PDF preserve supported Markdown headings, emphasis, lists, code and tables. Tables
repeat their header on subsequent pages. PowerPoint outlines use continuation slides and
editable tables; long content is not silently cut off. Text, Unicode, lists, table cells
and final preservation markers were checked in deterministic fixtures. HTML, remote
images, arbitrary Markdown extensions and custom designed decks are outside this export
contract. DOCX/PPTX font substitution may differ between installed Office applications;
the rendered checks use LibreOffice with Noto fonts.

PDF conversion uses local headless LibreOffice. The Docker image installs Writer,
Impress and Noto fonts. Native Windows can use an installed LibreOffice or a locally
built `traceform:local` image with Docker Desktop running. The conversion container has
no network access. If conversion is unavailable, the API returns an actionable error;
DOCX/Markdown/TXT exports remain available.

## Verification evidence

| Check | Result |
| --- | --- |
| PostgreSQL full backend suite | 423 passed; includes 16 Phase 5 cases |
| Docker SQLite regression suite | 420 passed; 3 PostgreSQL-only cases skipped; real PDF conversion passed |
| Final export formatter follow-up | All 17 Phase 5 cases passed in the container after the final emphasis-delimiter correction |
| Frontend contract/recovery tests | 22 passed |
| TypeScript, lint, production build | Passed |
| Two actual browser tabs | Autosave, stale-save rejection, recovery snapshot, latest-draft reload and restore backup passed |
| Saved versions | Save/reopen/compare, explicit device-copy import, exact-version mocked review and scoped regeneration passed |
| Browser downloads | DOCX and PDF from the restored draft; PPTX from a presentation outline received |
| Responsive layouts | Desktop plus 390×844 phone and 820×1180 tablet; no horizontal document overflow in inspected views |
| Export rendering | Four document pages and thirteen slide pages rendered and inspected; final text marker retained |
| Document skill renderer | `render_docx.py` also rendered every final DOCX page in the isolated renderer image |
| Production restart/readiness smoke | Passed: API restart during generation, database outage readiness, container restart and persisted state |
| Existing data | All original rows unchanged; backup and comparison recorded |

Export QA found and corrected PowerPoint text/footer overlap, unnecessary blank
continuation slides and inherited Word title styling. The real-converter PDF test
checks preserved word counts across page boundaries rather than assuming PDF extraction
keeps adjacent body words together across interleaved page footers.
The final formatter-only correction also removes complete bold/italic delimiters from
plain outline text; its regression case was added after the full-suite checkpoint.

Artifacts and logs:

- `.runtime/docker-verification/`: full database suites and production deployment smoke.
- `.runtime/phase5-preservation.json`: byte-for-byte comparison of common columns before
  and after additive migration `0006_artifact_versions`.
- `.runtime/phase5-exports/`: DOCX/PPTX/PDF fixtures, all rendered pages and extracted text.
- `frontend/.visual-check/phase5-*.png`: desktop history, conflicting draft, phone editor
  and tablet export screenshots. Screenshots show explicitly isolated test fixtures.
- `scripts/phase5_ui_fixture.py`: isolated SQLite/HTTP mock/worker browser test server.
- `scripts/verify_phase5_exports.py`: repeatable export fixtures and preservation checks.

The normal SQLite workspace has 23 sources, 38 generations, 51 artifacts, one preset
and two provider configurations. None were changed by Phase 5 verification. No Phase 5
fixture drafts, versions, reviews or jobs were inserted into that workspace. The normal
API, independent worker and frontend were restored after the UI tests.

## Remaining acceptance boundaries

- A successful external-provider end-to-end acceptance run is still pending. Mocked
  reviews verify the workflow and deterministic gates, not semantic model quality.
- Operator-private editing uses the existing API-key identity. Individual sign-in,
  sign-out, team workspaces and workspace isolation are Phase 7, not supplied by this phase.
- Export rendering was checked in LibreOffice; separate manual runs of desktop Microsoft
  Word and PowerPoint were not performed.
- No hosted frontend deployment, load benchmark or disaster recovery certification is
  implied by these local tests.
