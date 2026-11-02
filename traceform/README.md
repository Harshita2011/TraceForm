# TraceForm backend

FastAPI API, durable database worker, document ingestion, generation/review pipeline, teams, evidence, evaluations and recovery. See the [project README](../README.md) and [local development guide](../LOCAL_DEVELOPMENT.md) for setup.

Install `requirements.txt`, configure a private `.env` from `.env.example`, then run these commands in separate terminals from this directory:

```text
python -m db.migrate
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
python -m orchestrator.worker
```

Local development supports SQLite. Production uses PostgreSQL and a shared persistent storage directory and master key across API/worker processes. Normal queue dispatch does not require Redis/Celery. Production migrations run explicitly before service startup.

Run `python -m pytest tests -q` for isolated tests and `python eval/run_eval.py --version v1 --dry-run` to validate illustrative fixtures. Tests block paid provider network access. Never point reset-enabled tests at an application database.

See [PostgreSQL deployment](../POSTGRES_DEPLOYMENT.md), [encrypted recovery](../RECOVERY.md), and [Phase 8 verification](../PHASE8_VERIFICATION.md) for deployment requirements and open live-provider acceptance gates.
