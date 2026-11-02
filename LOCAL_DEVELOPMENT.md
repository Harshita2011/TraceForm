# Local development and worker operation

Use Python 3.11+ and Node 20+. Install dependencies in `traceform` with
`python -m pip install -r requirements.txt`, and in `frontend` with `npm ci`.
Copy each folder's `.env.example` to its documented local environment file.
Provider keys belong only in the backend environment or the Settings form.

On Windows, run `powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1`
from the repository root. It migrates the database, then starts the API, independent
worker and frontend as hidden processes. PIDs and logs are in `.runtime/`. The script
checks its saved PIDs before starting another process. Stop older manually started
services on ports 8000/3000 before using it for the first time. To stop script-started
services, stop their recorded PIDs (and the frontend's npm child process) in Task Manager.

For three separate terminals, the equivalent commands are:

```
cd traceform
python -m db.migrate
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

```
cd traceform
python -m orchestrator.worker
```

```
cd frontend
npm run dev
```

The API and worker must share DATABASE_URL, OBJECT_STORAGE_PATH and the encryption
master key. SQLite is supported for local development. PostgreSQL is the deployment
database. Normal dispatch uses a leased database queue; Redis/Celery are not required
for this path. Legacy Celery entry points remain for compatibility only. Do not run
legacy Celery dispatch against the same queued jobs.

For the PostgreSQL Compose deployment, required credentials, persistent volumes and
repeatable container verification, see [POSTGRES_DEPLOYMENT.md](POSTGRES_DEPLOYMENT.md).
Phase 4 evidence rules, review decisions and the remaining live-provider acceptance gate
are described in [PHASE4_VERIFICATION.md](PHASE4_VERIFICATION.md).
Server drafts, version actions, export dependencies and Phase 5 verification are described
in [PHASE5_VERIFICATION.md](PHASE5_VERIFICATION.md).

For PDF export on Windows, install LibreOffice or keep Docker Desktop running with a
current local image: `docker build -t traceform:local traceform` from the repository root.
Linux container deployments include LibreOffice and Noto fonts in the application image.
Markdown, TXT, DOCX and PPTX do not require a running conversion service.

## Settings and credentials

Settings supports Gemini/Anthropic, model discovery or manual model IDs, real connection
tests, and configurable USD-per-million input/output rates. Tests and saves may incur a
small provider charge. Only an administrator can edit. API_KEYS supports
`key:operator:admin,key:reader:analyst`; a single key has the admin role. Browser operator
keys remain server-side integration credentials for the legacy workspace. The browser
uses authenticated user sessions through the same-origin `/api/backend` proxy. Set
`NEXT_PUBLIC_API_URL=/api/backend` and server-only `TRACEFORM_API_URL=http://127.0.0.1:8000`
in the frontend environment. Remove `NEXT_PUBLIC_API_KEY` from browser configuration.

Open the dashboard and create the first owner using an administrator installation key,
your email and a password of at least 12 characters. This claims the existing legacy
workspace and keeps its sources and outputs. No user account is created by migration.
Owners invite teammates with one-time links and manage their roles under Team & workspace.
The original workspace owner manages installation-wide provider settings. See
[PHASE7_VERIFICATION.md](PHASE7_VERIFICATION.md) for permissions, approval and audit rules.

Keys are Fernet-encrypted in immutable configuration snapshots. The API returns only
whether a key is configured. Development creates `storage_data/.provider-master-key`
atomically. Back up this key separately and protect its filesystem permissions. Losing
it makes saved provider snapshots unreadable. In production set TRACEFORM_MASTER_KEY
(a Fernet key), API_KEYS, APP_ENV=production, and use TLS. Never commit keys or backups.
Changing/removing the active key affects new runs; jobs already queued keep their saved
provider snapshot. Revoke compromised credentials at the provider as well.

## Migrations and deployment

Back up the database and storage before upgrading. Run `python -m db.migrate` once before
starting services. The frozen baseline adopts existing tables without dropping data;
later revisions add queue/configuration/call records and cancellation status. Migrations
are repeatable and serialized with a PostgreSQL advisory lock. Destructive downgrades
are refused; restore a tested backup when rolling back a release.

Development checks migrations on startup. Production defaults to schema verification
only; explicit TRACEFORM_AUTO_MIGRATE=true enables automatic upgrades if desired.
Existing pre-queue runs remain historical and are never silently dispatched. Retry an
unfinished historical run to create a new durable job. Pin the same application release
for API and workers. Jobs refuse automatic resume if the pipeline fingerprint changes.

Docker Compose runs the independent worker. Set TRACEFORM_MASTER_KEY consistently for
both services and run migrations before production startup. Run several worker processes
for throughput; each process owns one job and output calls within it run concurrently.

## Recovery, cancellation and budgets

A job is saved atomically with its request and configuration. UI mutations send an
Idempotency-Key; repeating the same key/payload returns the same run. API clients should
keep the key when retrying a lost HTTP response. A changed payload needs a new key.
Retry/new-version actions create a new run with a fresh budget and current configuration.
Retry requests include only outputs that did not pass; originals remain intact.

Workers claim jobs with a compare-and-swap lease, heartbeat every five seconds and
recover expired leases after 60 seconds. TRACEFORM_JOB_TIMEOUT_SECONDS defaults to 1800.
Saved provider responses are replayed without new calls or usage increments. Completed
outputs are skipped. Extraction reuse requires matching source/sensitivity, model,
provider and analyst prompt/schema, plus valid source spans. A worker that lost its lease
cannot commit pipeline checkpoints or artifacts.

A crash during an external request leaves an unknown provider outcome. Such work fails
with guidance for an explicit retry; it is never silently repeated. Cancellation keeps
saved outputs and stops remaining work, but submitted provider requests can still bill.
This is duplicate-safe local execution, not a guarantee of exactly-once provider billing.

Calls reserve budget atomically before dispatch, across concurrent output/review calls.
The reservation estimates input tokens and maximum output; successful calls reconcile
reported usage using the job's saved pricing version. Rates are estimates, not invoices.
Unknown usage/outcomes retain reservations and are visibly flagged. Token estimates can
underestimate actual usage; overruns are disclosed and later calls are blocked when the
remaining cap cannot cover their reservation. Fixed provider plans, cached-token discounts,
and special context-tier pricing require rates appropriate to the provider agreement.


## Source library and creation presets (Phase 3)

Open `/dashboard/library` for uploads, filename search, sensitivity filters, paginated
results, extracted-text previews and reuse. Creation stays at `/dashboard/sources` and
can open a saved source through `?source=<uuid>`. Its four steps finish with a review of
source, privacy, formats, preferences and budget before any generation request.

Uploads extract synchronously: the UI shows Reading source, then Ready or an actionable
error. Failed files and creation preferences are kept for correction/retry. Text-based PDF,
DOCX, TXT and Markdown work without OCR. DOCX reads body paragraphs and tables in order;
headers, footers and embedded images are not extracted. Scanned/image-only PDFs must be
OCR'd first or supplied as images. Password-protected/restricted PDFs receive errors.

Uploads are limited to 50 MB and extracted text to 15,000 words or 90,000 characters,
whichever comes first. Longer text is rejected by default. The explicit truncation
checkbox keeps the leading text at a word boundary where possible and records the
warning on the source and in creation. Preview the retained text before using it.

Image OCR requires Tesseract installed and available on the server PATH, plus the
Python pytesseract/Pillow dependencies. This local machine does not currently expose
Tesseract on PATH. The UI discloses this requirement and missing/low-confidence OCR
returns an actionable error; no empty source is marked Ready. OCR confidence below
60% is rejected. Video uploads through the legacy API remain references only and cannot
be selected for generation; upload a transcript instead.

Move to trash is reversible and retains the stored file. Only unused sources can be
removed; any saved generation blocks removal to preserve source evidence, even when the
run failed or was cancelled. Restore is available from the Trash filter. There is no
permanent purge action in this phase. Generation admission serializes with removal and
rejects removed/reference-only sources.

Saved presets are private to the authenticated operator. They persist formats, audience,
tone, language, detail level, goal, additional section titles, brand name and writing
style. Source, sensitivity and spending limit are deliberately excluded. Update uses a
revision check; reload presets after a conflict. Removing a preset leaves existing runs
and their saved settings intact. Required format sections cannot be removed by a preset.

`GET /api/v1/generations/formats` supplies all 13 advertised contracts with versioned
required headings and written deliverable types. Presentation and infographic outputs
are outlines; video output is a written script, not generated media. A shared typed JSON
envelope and per-format structural checks reject malformed content, missing headings,
empty sections and automatic placeholder sections. Additional user sections are checked
too. A format failure prevents a Passed artifact, while fact/style/compliance results
remain independent. Structural validity is not a factual-accuracy guarantee. Richer
exports and deeper evidence/review work remain later phases.

## Combining documents (Phase 6)

Open Create output → Combine documents. Choose 2–8 saved sources and run the separately budgeted analysis. Inspect facts and conflicts, choose how disputed claims should be handled, then continue through creation. Saved collections and completed analyses can be reused. The strictest sensitivity applies. See [PHASE6_VERIFICATION.md](PHASE6_VERIFICATION.md) for limits and verification.

## Evaluation, operations and release

Open Evaluation to inspect recorded provider timings, known and unknown usage, date ranges and request failures. Benchmarks lets an owner/editor curate human claim/style assessments against exact saved versions and score them through the durable worker without provider calls. Results expose measurement versions and denominators. Historical/demo records do not become production measurements. See PHASE8_VERIFICATION.md for acceptance evidence, RECOVERY.md for encrypted maintenance backups and VERCEL_DEPLOYMENT.md for the deferred hosted release.

`python eval/run_eval.py --version v1 --dry-run` validates illustrative fixtures only. It does not generate benchmark quality scores. `python scripts/verify_live_release.py` explicitly contacts the already configured provider using invented text, an isolated database and a $0.15 per-run estimated-cost ceiling; it may incur charges. It never copies user documents. A provider-busy or evidence-review failure remains a failed acceptance result.
