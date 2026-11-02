"""Production-profile PostgreSQL smoke test using only an isolated DB and a local HTTP provider.

Run: python scripts/verify_postgres.py --url-file .runtime/pg-verification/test-url
Or:  python scripts/verify_postgres.py --url-env TEST_DATABASE_URL
Never points the application at the user's live SQLite database or a real AI provider.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKEND = Path(os.getenv('TRACEFORM_VERIFY_BACKEND', str(ROOT / 'traceform')))
sys.path.insert(0, str(BACKEND))


def verify(url, report_path):
    import asyncpg
    import httpx
    from cryptography.fernet import Fernet
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from db.migrate import migrate
    from agents.generators.blueprints import get_blueprint
    from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION

    parsed = make_url(url)
    if not parsed.drivername.startswith('postgresql') or not (parsed.database or '').startswith('traceform_test_'):
        raise ValueError('Use a dedicated PostgreSQL traceform_test_* database URL as the provisioning connection.')
    allowed_hosts = {'127.0.0.1', 'localhost'}
    if os.getenv('TRACEFORM_VERIFY_CONTAINER') == '1':
        allowed_hosts.add('postgres')
    if parsed.host not in allowed_hosts:
        raise ValueError('This smoke test only provisions databases on loopback.')
    database = 'traceform_test_deploy_' + uuid4().hex[:12]
    runtime = ROOT / '.runtime' / database
    runtime.mkdir(parents=True)
    target = parsed.set(database=database).render_as_string(hide_password=False)

    async def provision():
        admin = await asyncpg.connect(host=parsed.host, port=parsed.port or 5432,
            user=parsed.username, password=parsed.password, database=parsed.database)
        try:
            await admin.execute(f'CREATE DATABASE "{database}"')
        finally:
            await admin.close()
        engine = create_async_engine(target)
        try:
            await migrate(engine)
            await migrate(engine)
        finally:
            await engine.dispose()
    asyncio.run(provision())
    (runtime / 'database-url').write_text(target, encoding='utf8')
    (ROOT / '.runtime' / 'postgres-e2e-latest-url').write_text(target, encoding='utf8')

    analyst_started = threading.Event()
    release_analyst = threading.Event()
    requests = []
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            system = body.get('system', '')
            requests.append(system)
            if 'Knowledge Extraction analyst' in system:
                analyst_started.set()
                if not release_analyst.wait(30):
                    self.send_error(503)
                    return
                payload = MINIMAL_EXTRACTION.model_dump(mode='json')
                response_text = json.dumps(payload)
            elif 'Reply with OK' in system:
                response_text = 'OK'
            elif 'JSON OUTPUT SCHEMA' in system:
                content = '\n\n'.join('## ' + title + '\nAcme Corp launched Widget X.'
                    for title in get_blueprint('executive_summary').sections)
                response_text = json.dumps({'content':content, 'facts_used':[
                    {'claim':'Acme Corp launched Widget X.', 'source_span':'Acme Corp launched Widget X', 'fact_source_id':'f_1'}]})
            else:
                response_text = json.dumps({'passed':True, 'reasoning':'Verified synthetic fixture.',
                    'failing_claims':[], 'violations':[], 'issues':[], 'verified_claims':['Acme Corp launched Widget X.']})
            result = json.dumps({'id':'msg_local_verification', 'type':'message', 'role':'assistant',
                'model':'verification-model', 'content':[{'type':'text','text':response_text}],
                'stop_reason':'end_turn', 'stop_sequence':None, 'usage':{'input_tokens':10,'output_tokens':20}}).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(result)))
            self.end_headers()
            self.wfile.write(result)
    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    with socket.socket() as port_probe:
        port_probe.bind(('127.0.0.1', 0))
        api_port = port_probe.getsockname()[1]
    operator_key = secrets.token_hex(24)
    provider_key = 'local-synthetic-provider-key'
    env = {**os.environ, 'APP_ENV':'production', 'DATABASE_URL':target,
        'TRACEFORM_AUTO_MIGRATE':'false', 'TRACEFORM_MASTER_KEY':Fernet.generate_key().decode(),
        'API_KEYS':operator_key+':verification:admin', 'OBJECT_STORAGE_PATH':str(runtime/'storage'),
        'GEMINI_API_KEY':'', 'ANTHROPIC_API_KEY':provider_key, 'ANTHROPIC_MODEL':'verification-model',
        'ANTHROPIC_BASE_URL':f'http://127.0.0.1:{provider.server_port}',
        'TRACEFORM_ALLOW_SYNTHETIC_LLM':'false', 'NO_PROXY':'127.0.0.1,localhost',
        'PYTHONPATH':os.pathsep.join([str(BACKEND), str(BACKEND/'.runtime-deps')])}
    processes = []
    logs = []
    def start(name, args):
        stream = (runtime/(name+'.log')).open('w',encoding='utf8')
        logs.append(stream)
        process = subprocess.Popen([sys.executable,*args],cwd=BACKEND,env=env,
            stdout=stream,stderr=subprocess.STDOUT)
        processes.append(process)
        return process
    def stop(process):
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=10)
    client = httpx.Client(base_url=f'http://127.0.0.1:{api_port}', headers={'X-API-Key':operator_key},
        trust_env=False, timeout=10)
    def wait_ready():
        for _ in range(150):
            try:
                if client.get('/api/v1/healthz/ready').status_code == 200: return
            except httpx.TransportError:
                pass
            time.sleep(.1)
        raise AssertionError('API did not become ready; inspect '+str(runtime))
    def require(response, status=200):
        assert response.status_code == status, f'Unexpected HTTP status {response.status_code}; logs: {runtime}'
        return response.json()
    try:
        api = start('api-before-restart',['-m','uvicorn','api.main:app','--host','127.0.0.1','--port',str(api_port)])
        worker = start('worker',['-m','orchestrator.worker'])
        wait_ready()
        assert httpx.get(f'http://127.0.0.1:{api_port}/api/v1/sources/',trust_env=False).status_code == 401
        source = require(client.post('/api/v1/sources/',data={'text':'Acme Corp launched Widget X in the third quarter.','sensitivity':'public'}),201)
        preset = require(client.post('/api/v1/presets/',json={'name':'PostgreSQL verification',
            'settings':{'output_types':['executive_summary'],'params':{'tone':'formal','brand_name':'Acme'}}}),201)
        payload = {'source_id':source['id'],'output_types':['executive_summary'], 'budget_type':'tokens','budget_ceiling':100000}
        headers = {'Idempotency-Key':'production-postgres-verification'}
        run = require(client.post('/api/v1/generations/',json=payload,headers=headers),202)
        assert analyst_started.wait(15), 'Worker did not claim the queued run'
        stop(api)
        api = start('api-after-restart',['-m','uvicorn','api.main:app','--host','127.0.0.1','--port',str(api_port)])
        wait_ready()
        release_analyst.set()
        duplicate = require(client.post('/api/v1/generations/',json=payload,headers=headers),202)
        assert duplicate['id'] == run['id']
        for _ in range(200):
            result = require(client.get('/api/v1/generations/'+run['id']))
            if result['status'] not in {'queued','running','pending'}: break
            time.sleep(.1)
        assert result['status'] == 'completed', 'Synthetic pipeline failed; inspect '+str(runtime)
        assert len(result['artifacts']) == 1 and result['artifacts'][0]['review_status'] == 'passed'
        assert result['total_tokens'] == 150
        assert any(item['id']==preset['id'] for item in require(client.get('/api/v1/presets/')))
        assert client.delete('/api/v1/sources/'+source['id']).status_code == 409
        config = require(client.get('/api/v1/settings/provider'))
        assert config['key_configured'] and provider_key not in json.dumps(config)
        health = subprocess.run([sys.executable,'-m','orchestrator.worker','--healthcheck'],cwd=BACKEND,
            env=env,capture_output=True,timeout=10)
        assert health.returncode == 0
        stop(worker)
        cancelled = require(client.post('/api/v1/generations/',json=payload,headers={'Idempotency-Key':'cancel-postgres-verification'}),202)
        require(client.post('/api/v1/generations/'+cancelled['id']+'/cancel'))
        assert require(client.get('/api/v1/generations/'+cancelled['id']))['status'] == 'cancelled'
        async def inspect_saved():
            engine = create_async_engine(target)
            try:
                async with engine.connect() as db:
                    ciphertext = (await db.execute(text('SELECT encrypted_key FROM provider_configurations'))).scalar_one()
                    assert ciphertext != provider_key and provider_key not in ciphertext
                    count = (await db.execute(text('SELECT count(*) FROM llm_calls'))).scalar_one()
                    assert count == 5
            finally: await engine.dispose()
        asyncio.run(inspect_saved())
        report = {'postgres_database':database,'production_profile':True,'provider':'local HTTP mock; no external calls',
            'migrations_repeatable':True,'api_restart_during_generation':True,'duplicate_returns_same_run':True,
            'worker_completed_run':True,'worker_healthcheck':True,'source_and_preset_persisted':True,
            'cancelled_enum_persisted':True,'credential_encrypted':True,'provider_calls_recorded':5,
            'tokens_recorded':150,'generation_id':run['id'],'cancelled_generation_id':cancelled['id']}
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(report,indent=2))
    finally:
        release_analyst.set()
        for process in reversed(processes): stop(process)
        client.close();provider.shutdown();provider.server_close()
        for stream in logs: stream.close()

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--url-file',type=Path)
    source.add_argument('--url-env')
    parser.add_argument('--report',type=Path,default=ROOT/'.runtime/postgres-deployment-report.json')
    args=parser.parse_args()
    connection=args.url_file.read_text().strip() if args.url_file else os.environ[args.url_env]
    verify(connection,args.report)
