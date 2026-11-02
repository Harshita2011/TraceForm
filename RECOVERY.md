# Encrypted backup and recovery

`scripts/recovery.py` creates a whole-instance logical snapshot of every application table, file storage and the provider encryption master key. It supports SQLite and PostgreSQL. It encrypts the bundle using a separate Fernet recovery key and checksums every entry. The current format is `traceform-recovery:1`, capped at 256 MiB of uncompressed bundle content. For larger installations use coordinated database-native snapshots, file storage snapshots and separately protected secret backups; this tool is intentionally bounded.

## Maintenance backup

Stop new admissions, let jobs finish or cancel them, then stop the API and every worker using this installation. No process may write during the snapshot. The tool requires `--confirm-stopped` and refuses queued/running jobs. In Compose, stop API/worker while leaving PostgreSQL available. Run recovery from a maintenance process using the matching application version and access to its storage volume. Keep the database URL in a private file, not a command line or committed document.

Generate a separate recovery key in a private location (Python `Fernet.generate_key()`), and keep it separately from the bundle. Supply the exact provider master key in another private file. Production uses `TRACEFORM_MASTER_KEY`; local development may use `storage_data/.provider-master-key`. Losing the provider master key makes saved provider credentials unreadable. The encrypted bundle includes it; protect the recovery key accordingly.

From the repository root:

```
python scripts/recovery.py backup --url-file PRIVATE_DATABASE_URL_FILE --storage ABSOLUTE_STORAGE_DIRECTORY --master-key-file PRIVATE_PROVIDER_MASTER_KEY_FILE --key-file PRIVATE_RECOVERY_KEY_FILE --output NEW_BACKUP.tfbackup --confirm-stopped
```

The command refuses an existing output filename, missing linked source/output files, references outside storage, storage symlinks and incompatible tables. It records table counts, schema revision and encrypted bundle hash without logging credentials. File storage must not change during backup. Backup environment configuration separately: this bundle does not include `.env`, database credentials, hosting configuration or external services. Protect those files independently. Exclude the recovery destination from storage (or put it under the reserved `backups` subdirectory).

## Restore into a separate target

Use the application version matching the bundle revision. Provide an empty storage directory and a new SQLite file path or a PostgreSQL database with no tables. Stop all services for this target. The restore refuses existing data; it never overwrites the live database. It verifies encryption, checksums, archive paths, schema revision, every table count and file references, then reconstructs rows in dependency order. Legacy file references are remapped to restored storage object keys.

```
python scripts/recovery.py restore --url-file PRIVATE_NEW_DATABASE_URL_FILE --storage NEW_EMPTY_STORAGE_DIRECTORY --key-file PRIVATE_RECOVERY_KEY_FILE --bundle BACKUP.tfbackup --confirm-stopped
```

On success, point the **target** API and worker at the restored database/storage. For production set `TRACEFORM_MASTER_KEY` to the recovered `.provider-master-key` value using your deployment secret manager; do not print it. Retain authorized installation keys and origin settings from the separately protected deployment configuration. Run readiness and worker healthchecks; sign in with an existing restored account. Inspect sources, drafts, exact saved versions, approvals, comments, activity and an export. Confirm counts and credentials before switching any traffic.

If restoration fails partway, keep the failed target isolated and inspect the cause. Provision another empty target for retry; the tool intentionally refuses to reuse a partially populated target. Do not point normal services at it. Keep the source untouched until recovery acceptance finishes.

## Verification

`traceform/tests/test_measurements_recovery.py` exercises encrypted restoration of users, password hashes, sources, drafts, saved versions, version-bound approval decisions, comments, audit records, files and encrypted provider credentials. It signs in against the restored database, reads those resources and exports the exact saved version. The Docker PostgreSQL workflow also runs this test against a new dedicated PostgreSQL restore database, separate from its source test database. No external provider is contacted.

The real local workspace was cold-snapshotted, migrated and restored separately in Phase 8. Private evidence and recovery material are under `.runtime/phase8-recovery/` and excluded from git. Move any recovery key and retained backup to independent protected storage before relying on them for disaster recovery; colocated local verification files do not protect against disk loss.
