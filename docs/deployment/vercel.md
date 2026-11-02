# Vercel frontend deployment

Live deployment was deferred by the user on 2 November 2026. No Vercel project, domain, account resource or public backend was created. These instructions prepare the existing application for deployment later.

## Deployment layout

Deploy the Next.js frontend with Vercel. Keep the API and independent worker running from the same backend image, with PostgreSQL, durable storage and the same provider encryption key. The existing Compose stack is verified locally; it needs a backend host with persistent storage and a public HTTPS endpoint. This repository does not configure Vercel Daemons or a managed database/storage service. Hosting those components requires choosing and verifying the actual services.

Import the repository into Vercel and set **Root Directory** to `frontend`. Use Next.js, `npm ci`, `npm run build` and the default Next output. `frontend/vercel.json` supplies build settings. Set these environment variables for the intended environment, then rebuild:

| Variable | Value |
| --- | --- |
| `TRACEFORM_API_URL` | Private server-side variable: public HTTPS origin of the deployed API, without a trailing slash |
| `NEXT_PUBLIC_API_URL` | `/api/backend` |
| `NEXT_PUBLIC_UPLOAD_MAX_BYTES` | `4000000` |
| `NEXT_PUBLIC_USE_MOCK` | `false` |

Never put provider keys, `API_KEYS`, `DATABASE_URL` or `TRACEFORM_MASTER_KEY` in `NEXT_PUBLIC_*` variables. Browser requests use the same-origin proxy and an HttpOnly session cookie. Only the first-owner setup forwards an explicitly entered installation admin key; the proxy does not inject an installation-wide key into browser requests.

## Backend configuration

Follow [PostgreSQL deployment guide](postgresql.md) for the image, migration service, API, worker and persistent volumes. Configure `APP_ENV=production`, `TRACEFORM_AUTO_MIGRATE=false`, an explicit strong `API_KEYS`, `TRACEFORM_MASTER_KEY`, and `TRACEFORM_WEB_ORIGINS=https://YOUR-PROJECT.vercel.app,https://YOUR-DOMAIN`. Include each authorized preview origin explicitly if previews must write to this backend. Run `python -m db.migrate` once before starting services from the matching image. Schema head is `0009_measured_evaluations`.

Terminate HTTPS at the backend ingress and proxy to the loopback-bound API port. Keep PostgreSQL private and share the same storage volume between API and worker. Check `/api/v1/healthz/ready` and the worker healthcheck separately. Readiness alone does not prove an external provider can generate a verified output.

## Hosted limits and checks

The file picker defaults to a 4,000,000-byte upload ceiling so multipart overhead stays under the hosted function payload budget. The hosted proxy rejects a declared request size above 4,250,000 bytes before buffering it. Missing or non-HTTPS backend configuration returns a clear 503. API dataset/execution detail pages return at most five cases per request; dataset creation still needs to fit the platform's body limit. Very large curated datasets should be split across smaller versioned datasets. The backend's separate 50 MiB parser limit does not raise Vercel's proxy limit.

The proxy streams responses and preserves content-disposition and request IDs. Actual hosted large exports, session cookies, preview origins, runtime duration and upload limits must be checked against the chosen Vercel plan before production release. Platform documentation: [function limitations](https://vercel.com/docs/functions/limitations), [monorepo root configuration](https://vercel.com/docs/monorepos), [Daemons](https://vercel.com/docs/daemons).

## Release acceptance after URLs exist

1. Confirm frontend build, backend migration, API readiness and worker heartbeat.
2. Complete first-owner setup in the UI; sign in and verify a viewer cannot write.
3. Upload a small synthetic source, generate one output with an explicit small budget and inspect provider calls, claims and review results. Exercise failure, cancellation and retry.
4. Save a version, review/approve it and export TXT/DOCX/PDF; check response headers and actual file content.
5. Curate and score a dataset, inspect results and confirm recomputation matches. Test empty and invalid date ranges.
6. Verify cross-workspace isolation, HTTPS cookies, exact allowed origins and the documented upload boundary.
7. Make an encrypted backup and restore it into a separate environment using [recovery guide](recovery.md). Never restore over the live installation.

Until these hosted checks pass, the deployment remains prepared, not production verified.
