"""Verify the isolated traceform-pgverify Compose stack; never resets the app database.

Run after building/starting it with the generated verification env file.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main(env_file):
    runtime = ROOT / '.runtime' / 'docker-verification'
    runtime.mkdir(parents=True, exist_ok=True)
    base = ['docker', 'compose', '--project-name', 'traceform-pgverify', '--env-file',
            str(env_file), '-f', str(ROOT / 'traceform/docker-compose.yml')]

    def compose(*args, timeout=180, log=None):
        result = subprocess.run([*base, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        if log:
            (runtime / log).write_text(result.stdout + result.stderr, encoding='utf8')
        if result.returncode:
            raise RuntimeError(f'Compose operation failed (exit {result.returncode}); inspect {runtime / (log or "service logs")}')
        return result.stdout

    def healthy():
        for _ in range(90):
            states = [json.loads(line) for line in compose('ps', '--format', 'json').splitlines() if line.strip()]
            if all(any(s.get('Service') == name and s.get('Health') == 'healthy' for s in states)
                   for name in ('postgres', 'api', 'worker')):
                return
            time.sleep(1)
        raise AssertionError('Compose services did not become healthy')

    healthy()
    print('PostgreSQL, API and worker healthy.', flush=True)
    compose('exec', '-T', 'api', 'python', '-c',
            "import os,pathlib,pytesseract; assert os.getuid()!=0; "
            "assert not pathlib.Path('/app/.env').exists(); "
            "assert not pathlib.Path('/app/traceform.db').exists(); "
            "print('Tesseract:',pytesseract.get_tesseract_version())", log='image-check.log')
    compose('exec', '-T', 'api', 'python', '-c',
            "from pathlib import Path; Path('/app/storage_data/deployment-verification.txt').write_text('Synthetic volume persistence fixture.')")
    # A fresh disposable database, separate from the deployed traceform database.
    existing = compose('exec', '-T', 'postgres', 'psql', '-U', 'traceform', '-d', 'postgres',
                       '-Atc', "SELECT 1 FROM pg_database WHERE datname='traceform_test_docker'")
    if not existing.strip():
        compose('exec', '-T', 'postgres', 'createdb', '-U', 'traceform', 'traceform_test_docker')
    test_command = ('export TEST_DATABASE_URL="${DATABASE_URL%/traceform}/traceform_test_docker"; '
                    'exec python -m pytest tests -q -o cache_dir=/tmp/pytest_cache')
    compose('run', '--rm', '--no-deps', '-e', 'APP_ENV=test', '-e', 'API_KEYS=test-key',
            '-e', 'ANTHROPIC_API_KEY=sk-ant-test-placeholder', '-e', 'ANTHROPIC_MODEL=claude-opus-4-5',
            '-e', 'TRACEFORM_RESET_TEST_DATABASE=1', '--entrypoint', 'sh', 'api', '-c', test_command,
            timeout=600, log='pytest-postgres.log')
    print('Full PostgreSQL backend suite passed.', flush=True)
    compose('run', '--rm', '--no-deps', '-e', 'APP_ENV=test', '-e', 'API_KEYS=test-key',
            '-e', 'ANTHROPIC_API_KEY=sk-ant-test-placeholder', '-e', 'ANTHROPIC_MODEL=claude-opus-4-5',
            '-e', 'DATABASE_URL=sqlite+aiosqlite:////tmp/traceform_smoke.db', '--entrypoint', 'python',
            'api', '-m', 'pytest', 'tests', '-q', '-o', 'cache_dir=/tmp/pytest_cache', timeout=600, log='pytest-sqlite.log')
    print('SQLite regression suite passed.', flush=True)
    smoke = ('export TEST_DATABASE_URL="${DATABASE_URL%/traceform}/traceform_test_docker"; '
             'exec python scripts/verify_postgres.py --url-env TEST_DATABASE_URL '
             '--report /app/.runtime/production-smoke-report.json')
    # Linux bind mounts retain host ownership; run this disposable smoke process
    # as the caller so its report directory remains private and writable in CI.
    smoke_user = ['--user', f'{os.getuid()}:{os.getgid()}'] if hasattr(os, 'getuid') else []
    compose('run', '--rm', '--no-deps', *smoke_user, '-v', f'{ROOT / "scripts"}:/app/scripts:ro',
            '-v', f'{runtime}:/app/.runtime', '-e', 'TRACEFORM_VERIFY_BACKEND=/app',
            '-e', 'TRACEFORM_VERIFY_CONTAINER=1', '--entrypoint', 'sh', 'api', '-c', smoke,
            timeout=180, log='production-smoke.log')
    print('Production generation and API restart smoke passed.', flush=True)
    compose('stop', 'postgres', log='database-stop.log')
    readiness_probe = (
        "import urllib.request, urllib.error\n"
        "try:\n"
        "    urllib.request.urlopen('http://127.0.0.1:8000/api/v1/healthz/ready', timeout=5)\n"
        "except urllib.error.HTTPError as error:\n"
        "    assert error.code == 503, error.code\n"
        "else:\n"
        "    raise AssertionError('Database outage must fail readiness')\n"
    )
    compose('exec', '-T', 'api', 'python', '-c', readiness_probe, log='readiness-outage.log')
    compose('restart', 'postgres', 'api', 'worker', log='restart.log')
    healthy()
    compose('exec', '-T', 'worker', 'python', '-c',
            "from pathlib import Path; assert Path('/app/storage_data/deployment-verification.txt').read_text()=='Synthetic volume persistence fixture.'")
    # Check the smoke database after a PostgreSQL container restart.
    report = json.loads((runtime / 'production-smoke-report.json').read_text())
    db_name = report['postgres_database']
    assert db_name.startswith('traceform_test_deploy_') and db_name.replace('_', '').isalnum()
    rows = compose('exec', '-T', 'postgres', 'psql', '-U', 'traceform', '-d', db_name,
                   '-Atc', 'SELECT status FROM generations ORDER BY status::text').splitlines()
    assert sorted(rows) == ['CANCELLED', 'COMPLETED'], rows
    counts = compose('exec', '-T', 'postgres', 'psql', '-U', 'traceform', '-d', db_name,
                     '-Atc', 'SELECT (SELECT count(*) FROM sources), (SELECT count(*) FROM creation_presets)')
    assert counts.strip() == '1|1'
    report.update(container_restart_persistence=True, compose_services_healthy=True,
                  readiness_rejects_database_outage=True,
                  non_root_runtime=True, local_env_and_database_excluded=True,
                  shared_storage_persisted=True,
                  postgres_image='postgres:15-alpine', docker_build=True)
    report['postgres_version'] = compose('exec', '-T', 'postgres', 'psql', '-U', 'traceform',
                                        '-d', 'postgres', '-Atc', 'SHOW server_version').strip()
    (runtime / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print('Container restart persistence passed. Report: ' + str(runtime / 'report.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path, required=True)
    main(parser.parse_args().env_file)
