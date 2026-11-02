# TraceForm

TraceForm turns source documents into deliverables with source references, review results, saved versions and team approval workflows. It combines a Next.js frontend with a FastAPI API, an independent durable worker and SQLite for local development or PostgreSQL for deployment.

## What is included

- PDF, DOCX, TXT and Markdown ingestion; reusable source library and creation presets.
- Multiple output formats, multi-source analysis and explicit conflict handling.
- Budgeted provider calls, durable job progress, cancellation and retry.
- Source passage inspection, review findings, editable drafts, immutable versions and exports.
- Authenticated workspaces, member roles, invitations, comments, approvals and activity history.
- Versioned human-adjudicated benchmark datasets and an operations dashboard with recorded usage and timings.
- Additive database migrations, encrypted recovery bundles and automated release checks.

A source reference is inspectable evidence, not a guarantee of truth. Failed or incomplete reviews remain visible. Benchmark measurements state their human provenance, sample sizes and definitions.

## Current status

Phase 8 implementation is verified locally. The latest container suites passed **459 PostgreSQL tests** and **456 SQLite tests / 3 PostgreSQL-only skips**. The frontend passed **36 tests**, lint, TypeScript and its production build. Container/API restart, database-outage readiness and encrypted recovery were also checked.

**Open release gates:** reliable live verified-output acceptance still needs claim-to-output reference alignment. Real provider calls produce saved drafts, but the latest live acceptance remains marked needs-review. Vercel deployment and hosted acceptance are explicitly deferred. See [Phase 8 verification](PHASE8_VERIFICATION.md) and the [feature ledger](FEATURE_LEDGER.md) for evidence and limitations. Local verification is not a claim that hosted production acceptance passed.

## Local setup

Use Python 3.11+ and Node.js 22+. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r traceform/requirements.txt
npm --prefix frontend ci
Copy-Item traceform/.env.example traceform/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Edit the backend `.env`: configure a real provider and replace `API_KEYS` with a generated installation administrator key in the form `YOUR_RANDOM_KEY:administrator:admin`. Keep provider keys and the encryption master key on the backend. The frontend's normal API URL is `/api/backend`, with server-only `TRACEFORM_API_URL=http://127.0.0.1:8000`.

On Windows, start the API, worker and frontend together:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -Python .venv/Scripts/python.exe
```

Open [the local workspace](http://localhost:3000/dashboard/generations). Complete first-owner setup with your own credentials and the installation administrator key. The setup preserves existing sources and outputs. The API and worker must use the same database, storage directory, master key and application release.

For separate terminals, run the following backend commands from `traceform/`, using the configured environment, and the frontend command from the root:

```text
python -m db.migrate
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
python -m orchestrator.worker
npm run dev
```

The API and worker are separate long-running processes. Normal durable dispatch does not require Redis or Celery. PDF exports need LibreOffice; OCR needs Tesseract. The backend Docker image includes these system dependencies. See [local development](LOCAL_DEVELOPMENT.md) for complete operation, limits and troubleshooting.

## Checks

```powershell
cd traceform
python -m pytest tests -q
python eval/run_eval.py --version v1 --dry-run
cd ../frontend
npm test
npm run lint
npx tsc --noEmit
npm run build
```

The fixture validator checks illustrative data; it does not generate factual-accuracy scores. Automated suites block external provider calls. The separate `scripts/verify_live_release.py` uses invented text and the already configured provider with a USD 0.15 estimated-cost ceiling per run; running it can incur provider charges.

GitHub Actions runs the full SQLite and frontend checks. The separate PostgreSQL Compose workflow exercises both databases and production-profile restart/recovery checks. These workflows are configured; their GitHub results are separate from the recorded local runs.

## Repository layout

| Path | Purpose |
| --- | --- |
| `frontend/` | Next.js interface, authenticated API proxy and browser transport tests |
| `traceform/` | FastAPI, ingestion, generation/review, durable worker, teams and migrations |
| `scripts/` | Local startup, isolated verification and encrypted recovery tools |
| `.github/workflows/` | Automated backend/frontend and PostgreSQL deployment checks |
| `phases/` | Original phase specifications; current completion status is in the feature ledger |

## Deployment and recovery

- [PostgreSQL and Docker](POSTGRES_DEPLOYMENT.md): persistent API/worker/database deployment and isolated verification.
- [Vercel preparation](VERCEL_DEPLOYMENT.md): frontend root directory, HTTPS backend, environment variables and hosted limits. No live Vercel deployment is claimed.
- [Encrypted recovery](RECOVERY.md): stopped-writer backups and restoration into a separate empty target.
- [Implementation plan](IMPLEMENTATION_PLAN.md): feature phases and release acceptance criteria.

Environment files, private keys, local databases, uploads, generated evaluation reports, recovery bundles, runtime logs and build output are excluded from version control. Commit only placeholder environment examples. Do not include credentials or private source documents in issues or pull requests.
