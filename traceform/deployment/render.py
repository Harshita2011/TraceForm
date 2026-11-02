"""One disk-backed Render service: migrate, then supervise API and worker."""
import asyncio
import contextlib
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
from urllib.parse import urlsplit
from uuid import uuid4


def configure():
    from cryptography.fernet import Fernet
    from db.connection import connection_settings

    raw = os.environ.get("DATABASE_URL", "")
    try:
        url, _ = connection_settings(raw)
        if url.drivername != "postgresql+asyncpg" or not url.host or not url.database:
            raise ValueError()
        if "-pooler." in url.host:
            raise ValueError()
    except Exception:
        raise ValueError("DATABASE_URL must be a direct PostgreSQL URL (disable Neon connection pooling).") from None
    try:
        Fernet(os.environ.get("TRACEFORM_MASTER_KEY", "").encode())
    except Exception:
        raise ValueError("Set TRACEFORM_MASTER_KEY to a generated Fernet key.") from None
    keys = os.environ.get("API_KEYS", "").split(",")
    if not any(len(key.split(":")[0].strip()) >= 32 and
               (len(key.split(":")) == 1 or key.strip().endswith(":admin")) for key in keys):
        raise ValueError("API_KEYS must include a random installation admin key of at least 32 characters.")
    origins = os.environ.get("TRACEFORM_WEB_ORIGINS", "").split(",")
    for origin in origins:
        parsed = urlsplit(origin.strip())
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("TRACEFORM_WEB_ORIGINS must contain exact HTTPS origins without trailing slashes.")
    port = int(os.environ.get("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535.")
    os.environ.update(APP_ENV="production", TRACEFORM_AUTO_MIGRATE="false",
                      OBJECT_STORAGE_PATH="/var/data/traceform", PYTHONUNBUFFERED="1")
    return port


def prepare_storage():
    mount = Path("/var/data")
    if not mount.is_mount():
        raise ValueError("Attach a persistent disk at /var/data before starting this service.")
    folder = mount / "traceform"
    if folder.is_symlink():
        raise ValueError("Storage directory must not be a symlink.")
    folder.mkdir(exist_ok=True)
    if os.getuid() == 0:
        # Only the dedicated directory, never recursively change existing files.
        os.chown(folder, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    with tempfile.TemporaryFile(dir=folder) as probe:
        probe.write(b"storage probe")
        probe.flush()


async def stop_process(process):
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), timeout=20)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


async def supervise(port):
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopped.set)
    children = []
    tasks = []

    async def spawn(*args, **kwargs):
        process = await asyncio.create_subprocess_exec(
            sys.executable, *args, start_new_session=True, **kwargs)
        children.append(process)
        return process

    try:
        print("Applying database migrations.", flush=True)
        migration = await spawn("-m", "db.migrate")
        migration_wait = asyncio.create_task(migration.wait())
        stop_wait = asyncio.create_task(stopped.wait())
        tasks.extend([migration_wait, stop_wait])
        done, _ = await asyncio.wait(tasks, timeout=180, return_when=asyncio.FIRST_COMPLETED)
        if stopped.is_set():
            return 0
        if migration_wait not in done or migration.returncode != 0:
            print("Migration failed or timed out; API and worker were not started.", flush=True)
            return 1
        worker_id = f"{socket.gethostname()}:render:{uuid4().hex}"
        worker = await spawn("-m", "orchestrator.worker", env=dict(os.environ, TRACEFORM_WORKER_ID=worker_id))
        env = dict(os.environ, TRACEFORM_REQUIRED_WORKER_PREFIX=worker_id)
        api = await spawn("-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", str(port), env=env)
        watches = [asyncio.create_task(p.wait()) for p in (worker, api)]
        tasks.extend(watches)
        await asyncio.wait([stop_wait, *watches], return_when=asyncio.FIRST_COMPLETED)
        if stopped.is_set():
            return 0
        print("A critical process exited; stopping the service for restart.", flush=True)
        return 1
    finally:
        await asyncio.gather(*(stop_process(p) for p in children))
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


def main():
    try:
        port = configure()
        prepare_storage()
    except (ValueError, OSError):
        # Avoid logging database URL, credentials, or arbitrary exception strings.
        print("Invalid deployment configuration. Check direct DATABASE_URL, Fernet master key, admin API_KEYS, HTTPS origins and /var/data disk.", flush=True)
        return 1
    return asyncio.run(supervise(port))


if __name__ == "__main__":
    raise SystemExit(main())
