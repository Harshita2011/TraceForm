# PostgreSQL deployment

The backend Compose stack runs PostgreSQL 15, a one-shot migration, the API and
an independent durable worker. It does not start the Next.js frontend. The API
binds to loopback by default; put your authenticated frontend/proxy in front of it
for remote access.

## Configure and start

Copy `traceform/.env.deploy.example` to a private deployment env file. Set:

- `POSTGRES_PASSWORD`: a randomly generated URL-safe password (hex is suitable).
- `API_KEYS`: a random operator key followed by `:administrator:admin`.
- `TRACEFORM_MASTER_KEY`: a Fernet key, generated once and retained with backups.
- Provider credentials/model settings for the provider you intend to use.
- `API_PORT`: an unused local port if 8000 already serves your development app.

Generate values using Python's `secrets.token_hex(32)` and
`cryptography.fernet.Fernet.generate_key().decode()`. Keep them out of Git.
The image excludes env files, local databases, keys and source storage.

From the repository root, replacing `<env-file>` with the private file path:

```powershell
docker compose --env-file <env-file> -f traceform/docker-compose.yml config --quiet
docker compose --env-file <env-file> -f traceform/docker-compose.yml up -d --build
docker compose --env-file <env-file> -f traceform/docker-compose.yml ps --all
```

The migration must exit successfully before the API and worker start. Production
startup checks the schema version rather than silently migrating it. Readiness is
`GET /api/v1/healthz/ready`; it returns 503 if the database cannot be reached.
Worker health checks require a recent heartbeat from that container.

## Team sessions and frontend proxy

Phase 7 adds migration `0008_team_workspaces`. Existing business rows receive the
`legacy` workspace ID; the first owner claims that workspace through the setup screen.
Migration creates no real accounts or passwords. Back up before upgrading.

Keep `API_KEYS` server-side for installation administration and legacy integrations.
The frontend uses `NEXT_PUBLIC_API_URL=/api/backend` and server-only `TRACEFORM_API_URL`
pointing to the API. Installation keys are entered only for initial owner setup.
Set `TRACEFORM_WEB_ORIGINS` to the exact frontend HTTPS origin(s), comma separated.
Production session cookies require HTTPS. Protect the API behind the frontend/reverse
proxy, and apply a shared edge login limit when running several API replicas; the
built-in bounded login throttle is per process. Invite links are shared manually,
expire after three days, and can be revoked in the team screen.

See [Phase 7 verification](../verification/phase-7.md) for role and approval semantics.

## Preserve data

PostgreSQL data and uploaded source files use separate named volumes. Keep the
same Compose project name when restarting or upgrading. Back up both volumes and
the master key together before an upgrade. Do not rotate the master key without
re-encrypting existing provider settings. Stopping/removing containers with
`docker compose down` preserves volumes; adding `--volumes` deletes them.

## Repeat deployment verification

Use a separate project named `traceform-pgverify`, a generated verification env
file and an unused API port. This keeps the user's running application separate.

```powershell
docker compose --project-name traceform-pgverify --env-file .runtime/pg-verification/compose.env -f traceform/docker-compose.yml up -d --build
python scripts/verify_docker.py --env-file .runtime/pg-verification/compose.env
```

The verifier creates `traceform_test_docker` and generated
`traceform_test_deploy_*` databases in that isolated PostgreSQL container. Run it
only on the dedicated verification volume; its fixed test database is reused and reset.
It runs the full PostgreSQL and SQLite suites, a production-profile pipeline with
a local HTTP mock provider, API restart/idempotency checks, and PostgreSQL
container restart persistence checks. It makes no paid provider calls. Reports
and logs are written to `.runtime/docker-verification/`.

External database tests may reset tables. They require a dedicated
`traceform_test_*` database and explicit `TRACEFORM_RESET_TEST_DATABASE=1`.
Never set these against a real application database.

The verification stack can be stopped with the same Compose command and `down`,
without `--volumes`, retaining evidence and test data for inspection.


## Phase 8 release additions

The current schema head is `0009_measured_evaluations`, adding immutable benchmark datasets/cases and durable evaluation executions/outcomes. Run migrations with the matching API/worker image before starting it. Scoring runs through the same independent worker and does not call providers.

The full container test suite includes encrypted SQLite and PostgreSQL backup/restore acceptance, restored login/draft/version/approval/comment/export checks, recorded operations and benchmark permissions. Restore tests create a dedicated `traceform_test_restore_*` database. See [recovery guide](recovery.md) for maintenance backups and empty-target recovery, [Phase 8 verification](../verification/phase-8.md) for current acceptance evidence, and [Vercel deployment guide](vercel.md) for the explicitly deferred hosted frontend/backend setup.
