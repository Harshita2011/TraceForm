"""Isolated local UI acceptance server. No real provider calls or application data writes."""
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'traceform'))
from dotenv import dotenv_values
from cryptography.fernet import Fernet
runtime = ROOT / '.runtime'
runtime.mkdir(parents=True, exist_ok=True)
master_path = runtime / 'phase5-ui-master-key'
new_master = not master_path.exists()
if new_master:
    master_path.write_bytes(Fernet.generate_key())
os.environ.update(APP_ENV='test', DATABASE_URL='sqlite+aiosqlite:///' + str(runtime / 'phase5-ui.db'),
    OBJECT_STORAGE_PATH=str(runtime / 'phase5-ui-storage'), API_KEYS=dotenv_values(ROOT / 'traceform/.env').get('API_KEYS', ''),
    TRACEFORM_MASTER_KEY=master_path.read_text().strip(), TRACEFORM_AUTO_MIGRATE='true',
    GEMINI_API_KEY='', ANTHROPIC_API_KEY='isolated-mock-key', ANTHROPIC_MODEL='phase5-local-fixture',
    TRACEFORM_ALLOW_SYNTHETIC_LLM='false', NO_PROXY='127.0.0.1,localhost')
from agents.generators.blueprints import get_blueprint
from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION
from revisions.content import digest


def document(output_type):
    return '\n\n'.join('## ' + heading + '\nAcme Corp launched Widget X.' for heading in get_blueprint(output_type).sections)


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        system = body.get('system', '')
        if 'Knowledge Extraction analyst' in system:
            payload = MINIMAL_EXTRACTION.model_dump(mode='json')
        elif 'Reply with OK' in system:
            payload = 'OK'
        elif 'map evidence' in system:
            payload = {'facts_used':[{'claim':'Acme Corp launched Widget X.', 'source_span':'Acme Corp launched Widget X',
                                     'start_char':0, 'end_char':len('Acme Corp launched Widget X')}]}
        elif 'revise one Markdown section' in system:
            payload = {'content':'Acme Corp launched Widget X.\n\nRecommendation: assess adoption before adding commitments.'}
        elif 'JSON OUTPUT SCHEMA' in system:
            payload = {'content':document('executive_summary'), 'facts_used':[{'claim':'Acme Corp launched Widget X.',
                'source_span':'Acme Corp launched Widget X'}]}
        else:
            payload = {'passed':True, 'reasoning':'Isolated mocked review. Not a live-provider acceptance result.',
                       'issues':[], 'failing_claims':[], 'violations':[], 'verified_claims':['Acme Corp launched Widget X.']}
        text = payload if isinstance(payload, str) else json.dumps(payload)
        response = json.dumps({'id':'msg_fixture', 'type':'message', 'role':'assistant', 'model':'phase5-local-fixture',
            'content':[{'type':'text', 'text':text}], 'stop_reason':'end_turn', 'stop_sequence':None,
            'usage':{'input_tokens':10, 'output_tokens':20}}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(response)))
        self.end_headers(); self.wfile.write(response)


provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
threading.Thread(target=provider.serve_forever, daemon=True).start()
os.environ['ANTHROPIC_BASE_URL'] = f'http://127.0.0.1:{provider.server_port}'
from db.session import engine, AsyncSessionLocal
from db.migrate import migrate
from db.models import Source, Generation, Artifact
from schemas.enums import SensitivityLevel, SensitivitySource, GenerationStatus, ArtifactReviewStatus


async def seed():
    await migrate(engine)
    # Adopt a pre-persistence synthetic fixture once; no application database is opened.
    if new_master:
        from sqlalchemy import select
        from db.models import ProviderConfiguration
        from security.credentials import encrypt_key
        async with AsyncSessionLocal() as db:
            for configuration in (await db.execute(select(ProviderConfiguration))).scalars():
                if configuration.provider != 'anthropic' or configuration.model != 'phase5-local-fixture':
                    raise RuntimeError('Refusing to change a provider that is not the isolated fixture.')
                configuration.encrypted_key = encrypt_key('isolated-mock-key')
            await db.commit()
    marker = runtime / 'phase5-ui-fixture.json'
    if not marker.exists():
        async with AsyncSessionLocal() as db:
            source = Source(filename='Phase5_UI_TEST_FIXTURE.txt', extracted_text='Acme Corp launched Widget X.',
                sensitivity=SensitivityLevel.PUBLIC, sensitivity_source=SensitivitySource.OPERATOR,
                extraction_method='Isolated local UI fixture')
            db.add(source); await db.flush()
            run = Generation(source_id=source.id, output_types=['executive_summary','presentation'], params={},
                status=GenerationStatus.COMPLETED, model_version='LOCAL MOCK — UI fixture', prompt_version='fixture')
            db.add(run); await db.flush()
            result = {'run_id':str(run.id), 'source_id':str(source.id)}
            for output_type in run.output_types:
                content = document(output_type)
                if output_type == 'presentation':
                    content += '\n\n## Export layout fixture\nUnicode हिंदी 中文 🧪\n\n| Item | Value |\n| --- | --- |\n| Test fixture | 42 |\n\n- First item\n- Second item'
                artifact = Artifact(generation_id=run.id, output_type=output_type, content=content,
                    review_results=[], facts_used=[], review_status=ArtifactReviewStatus.PENDING, cost={'total':0})
                db.add(artifact); await db.flush(); result[output_type] = str(artifact.id)
            await db.commit()
            marker.write_text(json.dumps(result), encoding='utf-8')
    await engine.dispose()


asyncio.run(seed())
from api.main import app
from orchestrator.queue import run_forever
worker = None


@app.on_event('startup')
async def start_fixture_worker():
    global worker
    worker = asyncio.create_task(run_forever())


@app.on_event('shutdown')
async def stop_fixture_worker():
    worker.cancel()
    await asyncio.gather(worker, return_exceptions=True)
    provider.shutdown()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
