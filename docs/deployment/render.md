# Render backend with Neon PostgreSQL

Run one Render Docker web service containing the API and durable generation worker. Neon stores database records; the Render disk stores uploaded documents and generated files. The frontend remains a separate Vercel project. This configuration prepares deployment; it does not provision resources or prove hosted acceptance.

## 1. Get the Neon connection string

In your Neon project, choose **Connect**, select the intended branch, database and role, and **disable connection pooling**. Copy the direct PostgreSQL connection string into Render's secret `DATABASE_URL` variable. Do not paste it into GitHub or chat.

Example only:

```text
postgresql://USER:PASSWORD@ep-YOUR-ENDPOINT.REGION.aws.neon.tech/neondb?sslmode=require
```

Use a dedicated database for this installation. Startup applies additive migrations to that database. Existing local SQLite records/files are not automatically transferred. Back up an existing database before upgrading.

The backend translates `postgresql://` and `postgres://` to SQLAlchemy's asyncpg driver and uses certificate and hostname verification for Neon TLS. Libpq's `sslmode` is translated; `channel_binding` is removed because asyncpg does not implement that libpq option. This deployment does not promise SCRAM channel binding. Keep a direct endpoint: the current prepared-statement and migration configuration is not verified against Neon's transaction pooler.

## 2. Create the Render service

Use **New → Blueprint**, connect the TraceForm GitHub repository and select the branch containing `render.yaml`. Review the paid service and disk before creating resources. The Blueprint uses a Standard service because document conversion and API/worker share memory. Monitor usage and adjust after measuring your workload.

For an existing/manual web service use these settings:

| Setting | Value |
| --- | --- |
| Runtime | Docker |
| Root directory | Repository root; leave blank |
| Dockerfile path | `./traceform/Dockerfile.render` |
| Docker build context | `.` |
| Docker command | Leave blank; use the image CMD |
| Instances | 1 |
| Persistent disk mount | `/var/data` |
| Disk size | 10 GB initially |
| Health check | `/api/v1/healthz/service` |
| Shutdown grace | 30 seconds |

Do not set a Uvicorn-only start command: it bypasses the worker and migrations. Do not add a pre-deploy migration command: the startup entry point runs migrations after the disk is attached. Disk-backed services have deployment downtime and cannot share that disk across separate API/worker services. Scaling later requires shared object storage and a revised deployment layout.

## 3. Set backend secrets

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Direct Neon URL from step 1 |
| `TRACEFORM_MASTER_KEY` | A generated Fernet key; keep unchanged across deploys |
| `API_KEYS` | `YOUR_RANDOM_INSTALLATION_KEY:administrator:admin` |
| `TRACEFORM_WEB_ORIGINS` | Exact Vercel HTTPS origin, e.g. `https://YOUR-PROJECT.vercel.app`, without a trailing slash; comma-separate additional authorized origins |

Generate the two keys locally, save them privately, and enter them in Render's environment settings:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The Blueprint sets `APP_ENV=production`, `TRACEFORM_AUTO_MIGRATE=false` and `OBJECT_STORAGE_PATH=/var/data/traceform`. Render supplies `PORT`; the supervisor honors it. Add provider credentials through the authenticated app settings after first-owner setup, or configure the supported provider environment variables privately on Render. Never regenerate the master key on every start: existing encrypted credentials would become unreadable.

Bootstrap creates only `/var/data/traceform`, assigns that directory to UID/GID 10001, then drops root. A missing mount, invalid configuration or failed migration prevents the API and worker from starting. Both processes share the database, key and disk. If either exits unexpectedly, the supervisor stops the sibling and exits unsuccessfully. Render's HTTP health check also checks this worker's fresh heartbeat and writable storage; a stale worker or unavailable database returns 503.

## 4. Connect Vercel and create the owner

After Render reports healthy, copy its public HTTPS service URL, for example `https://YOUR-SERVICE.onrender.com`. Set that value as **server-only** `TRACEFORM_API_URL` in Vercel, keep `NEXT_PUBLIC_API_URL=/api/backend`, and redeploy the frontend. See [Vercel setup](vercel.md).

Open the frontend and choose **Create account**. Enter your name, email and a password of at least 12 characters. Registration signs you into your own new private workspace without an invitation or installation key. Existing accounts can sign in normally.

The installation administrator can separately use **Installation admin setup** while signed out to claim legacy sources and outputs and manage shared provider configuration. That action requires the random installation key from `API_KEYS` (only the part before `:administrator:admin`). Public registrations do not receive installation-wide administration. Keep keys and passwords private. Public registration does not verify email ownership or send email; apply deployment-level abuse controls in addition to the backend's bounded registration throttle.

## Acceptance and recovery

Local startup verification is repeatable without Neon credentials or paid provider calls:

```powershell
docker build -t traceform:render-check -f traceform/Dockerfile.render .
python scripts/verify_render.py
```

The script creates a uniquely named, disposable Compose project, checks migrations/readiness, non-root processes, graceful restart, file persistence, database outage recovery and worker-crash shutdown. It binds only `127.0.0.1:18009`, stops its containers afterward, and leaves isolated volumes/private configuration under `.runtime` for inspection. GitHub Actions runs the same check for relevant changes. This does not test the live Neon account or Render service.

Local verification on 2 November 2026 passed all of those startup checks. The Render image's full SQLite regression suite passed **474 tests**, with **3 PostgreSQL-only tests skipped**. The startup check itself used real disposable PostgreSQL. Live Neon TLS connectivity and Render/Vercel acceptance remain pending deployment.

Check `/api/v1/healthz/service`, then complete the [hosted acceptance steps](vercel.md#release-acceptance-after-urls-exist): small upload, budgeted generation, provider-call accounting, cancellation/retry, exports and permissions. Restart the Render service and confirm files and records remain. A healthy service proves dependencies are available, not that external provider quality acceptance passed.

Back up both Neon and the files/key using the [recovery guide](recovery.md). A database-only backup cannot recover uploaded documents. Test restoration in a separate installation.

References: [Render Blueprint schema](https://render.com/docs/blueprint-spec), [persistent disks](https://render.com/docs/disks), [health checks](https://render.com/docs/health-checks), [Neon SQLAlchemy guide](https://neon.com/docs/guides/sqlalchemy), [asyncpg connection options](https://magicstack.github.io/asyncpg/current/api/index.html#asyncpg.connect).
