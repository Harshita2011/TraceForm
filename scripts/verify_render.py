"""Exercise the combined Render image against disposable local PostgreSQL.

Build first: docker build -t traceform:render-check -f traceform/Dockerfile.render .
No Neon credentials or external provider requests are used.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from cryptography.fernet import Fernet


def main(image, port):
    root = Path(__file__).resolve().parents[1]
    runtime = root / ".runtime" / "render-verification"
    runtime.mkdir(parents=True, exist_ok=True)
    # Each invocation owns a fresh, explicitly named project and its volumes.
    project = "traceform-renderverify-" + secrets.token_hex(4)
    password = secrets.token_hex(32)
    config = {"services": {
        "postgres": {"image": "postgres:15-alpine", "environment": {
            "POSTGRES_USER": "traceform", "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": "traceform_test_render"}},
        "backend": {"image": image, "ports": [f"127.0.0.1:{port}:10000"],
            "volumes": ["files:/var/data"], "environment": {
                "DATABASE_URL": f"postgresql://traceform:{password}@postgres/traceform_test_render",
                "TRACEFORM_MASTER_KEY": Fernet.generate_key().decode(),
                "API_KEYS": secrets.token_hex(32) + ":verification:admin",
                "TRACEFORM_WEB_ORIGINS": "https://verification.example.com"}}},
        "volumes": {"files": {}}}
    path = runtime / (project + ".json")
    path.write_text(json.dumps(config), encoding="utf8")
    base = ["docker", "compose", "-p", project, "-f", str(path)]

    def compose(*args):
        result = subprocess.run([*base, *args], capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError("Docker verification command failed; inspect the private runtime logs.")
        return result.stdout.strip()

    def status():
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/v1/healthz/service", timeout=3) as response:
                return response.status
        except HTTPError as exc:
            return exc.code
        except (URLError, TimeoutError, ConnectionError):
            return None

    def until(check, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if check():
                return
            time.sleep(1)
        raise AssertionError("Timed out waiting for a deployment contract.")

    def exec_python(code):
        return compose("exec", "-T", "backend", "python", "-c", code)

    def assert_stopped(expected_code):
        cid = compose("ps", "-a", "-q", "backend")
        def exited():
            result = subprocess.run(["docker", "inspect", "--format", "{{json .State}}", cid],
                                    capture_output=True, text=True, check=True)
            state = json.loads(result.stdout)
            return not state["Running"] and state["ExitCode"] == expected_code
        until(exited, 35)

    report = {"project": project, "checks": []}
    try:
        compose("up", "-d", "postgres")
        until(lambda: "accepting connections" in compose("exec", "-T", "postgres", "sh", "-c", "pg_isready -U traceform || true"))
        compose("up", "-d", "backend")
        until(lambda: status() == 200)
        # Inspect actual children: bootstrap must have dropped root before migration/API/worker.
        exec_python("from pathlib import Path; "
                    "children=[p for p in Path('/proc').iterdir() if p.name.isdigit() and "
                    "(p/'cmdline').read_bytes().split(b'\\0')[1:3] in ([b'-m',b'orchestrator.worker'],[b'-m',b'uvicorn'])]; "
                    "assert len(children)>=2; "
                    "assert all('Uid:\\t10001\\t10001' in (p/'status').read_text() for p in children if p.name!='1'); "
                    "assert not Path('/app/.env').exists(); "
                    "Path('/var/data/traceform/persistence.txt').write_text('synthetic persistence fixture')")
        report["checks"].append("migrations, API, worker, storage, non-root children and image hygiene")
        compose("stop", "-t", "25", "backend")
        assert_stopped(0)
        compose("start", "backend")
        until(lambda: status() == 200)
        exec_python("from pathlib import Path; assert Path('/var/data/traceform/persistence.txt').read_text()=='synthetic persistence fixture'")
        report["checks"].append("graceful shutdown and persistence after restart")
        compose("stop", "postgres")
        until(lambda: status() == 503, 20)
        compose("start", "postgres")
        until(lambda: status() == 200)
        report["checks"].append("database outage fails readiness and recovers")
        # Terminate only this test container's child. The parent must stop its sibling.
        exec_python("import os,signal; from pathlib import Path; "
                    "p=next(p for p in Path('/proc').iterdir() if p.name.isdigit() and "
                    "(p/'cmdline').read_bytes().split(b'\\0')[1:3]==[b'-m',b'orchestrator.worker']); "
                    "os.kill(int(p.name),signal.SIGKILL)")
        assert_stopped(1)
        compose("start", "backend")
        until(lambda: status() == 200)
        report["checks"].append("worker crash stops service; restart restores readiness")
        report["passed"] = True
        print(json.dumps(report), flush=True)
    finally:
        logs = subprocess.run([*base, "logs", "--no-color"], capture_output=True, text=True, timeout=30)
        (runtime / "service.log").write_text(logs.stdout + logs.stderr, encoding="utf8")
        (runtime / "report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
        # Preserve these isolated volumes for inspection; no user data is deleted.
        compose("down")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="traceform:render-check")
    parser.add_argument("--port", type=int, default=18009)
    args = parser.parse_args()
    main(args.image, args.port)
