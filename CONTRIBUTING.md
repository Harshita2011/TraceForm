# Contributing to TraceForm

Read [README.md](README.md) for setup and [FEATURE_LEDGER.md](FEATURE_LEDGER.md) for current scope and open release gates. Keep API, worker, migrations and feature UI changes consistent.

## Workflow

1. Create a branch from the default branch (`codex/` is the prefix used by coding-agent branches).
2. Make a focused change; include durable state, permissions, loading/error/read-only states and documentation when relevant.
3. Run checks appropriate to the change. The complete local commands are in the README.
4. Open a pull request using the repository template. Describe the resulting behavior, validation and unresolved limitations.

Tests must use isolated databases and mocked providers. PostgreSQL reset-enabled tests require a dedicated `traceform_test_*` database. Never run destructive test setup against the user's workspace. Run live provider acceptance only intentionally with invented text and an explicit budget; it can incur charges.

Do not commit `.env`, provider credentials, encryption/recovery keys, application databases, source uploads, private backups or runtime logs. Use only placeholder values in environment examples. Include safe reproduction steps and synthetic data in issues. Report sensitive security problems privately to a maintainer.

Preserve existing evidence and review outcomes. Do not remove blocking checks or turn missing/failed measurements into passing values merely to make a test or badge green. Database upgrades must be additive and versioned; document required maintenance and recovery steps.
