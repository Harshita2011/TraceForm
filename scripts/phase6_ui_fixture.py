"""Isolated Phase 6 UI acceptance server with a local HTTP provider and durable worker."""
import asyncio,json,os,re,sys,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'traceform'))
from dotenv import dotenv_values
from cryptography.fernet import Fernet
runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
master=runtime/'phase6-ui-master-key'
if not master.exists():master.write_bytes(Fernet.generate_key())
os.environ.update(APP_ENV='test',DATABASE_URL='sqlite+aiosqlite:///'+str(runtime/'phase6-ui.db'),
    OBJECT_STORAGE_PATH=str(runtime/'phase6-ui-storage'),API_KEYS=dotenv_values(ROOT/'traceform/.env').get('API_KEYS',''),
    TRACEFORM_MASTER_KEY=master.read_text().strip(),TRACEFORM_AUTO_MIGRATE='true',
    GEMINI_API_KEY='',ANTHROPIC_API_KEY='isolated-phase6-mock-key',ANTHROPIC_MODEL='phase6-local-fixture',
    TRACEFORM_ALLOW_SYNTHETIC_LLM='false',NO_PROXY='127.0.0.1,localhost')
from db.session import engine,AsyncSessionLocal
from db.migrate import migrate
from db.models import Source
from schemas.enums import SensitivityLevel,SensitivitySource
from sqlalchemy import select
from agents.generators.blueprints import get_blueprint
from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION

async def seed():
    await migrate(engine)
    async with AsyncSessionLocal() as db:
        sources=(await db.execute(select(Source).order_by(Source.filename))).scalars().all()
        if not sources:
            for suffix,count,sensitivity in [('A',12,SensitivityLevel.PUBLIC),('B',18,SensitivityLevel.INTERNAL)]:
                db.add(Source(filename=f'Phase6_Cedar_Report_{suffix}.txt',extracted_text=f'Cedar has {count} beds. Cedar opened in 2026.',
                    sensitivity=sensitivity,sensitivity_source=SensitivitySource.OPERATOR,extraction_method='text',content_type='text/plain'))
            await db.commit();sources=(await db.execute(select(Source).order_by(Source.filename))).scalars().all()
        result=[{'id':str(s.id),'text':s.extracted_text,'count':12 if '_A.' in s.filename else 18,'filename':s.filename} for s in sources]
    await engine.dispose()
    (runtime/'phase6-ui-fixture.json').write_text(json.dumps(result),encoding='utf-8')
    return result

SOURCES=asyncio.run(seed())

class Provider(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        system=body.get('system','');user=json.dumps(body.get('messages',[]),ensure_ascii=False)
        if 'Knowledge Extraction analyst' in system:
            source=next(s for s in SOURCES if s['text'] in user)
            result=MINIMAL_EXTRACTION.model_dump(mode='json');result['facts']=[]
            for claim in [f"Cedar has {source['count']} beds.",'Cedar opened in 2026.']:
                start=source['text'].index(claim)
                result['facts'].append({'claim':claim,'source_span':claim,'start_char':start,'end_char':start+len(claim),'confidence':1})
        elif 'compare source facts' in system:result={'conflicts':[]}
        elif 'Reply with OK' in system:result='OK'
        elif 'JSON OUTPUT SCHEMA' in system or 'map evidence' in system:
            # This provider only serves deterministic UI fixtures, never production claims.
            omitted='\\"choice\\": \\"omit\\"' in user or '"choice": "omit"' in user
            facts=[{'claim':f"Cedar has {s['count']} beds.",'source_span':f"Cedar has {s['count']} beds.",'source_id':s['id']} for s in SOURCES]
            content='Cedar has 12 beds. Cedar has 18 beds. Conflict: the reports disagree about the bed count; confirm their scope before deciding.'
            if omitted:
                facts=[{'claim':'Cedar opened in 2026.','source_span':'Cedar opened in 2026.','source_id':SOURCES[0]['id']}]
                content='Cedar opened in 2026. Disputed bed counts are omitted pending reconciliation.'
            result={'facts_used':facts,'content':'\n\n'.join('## '+heading+'\n'+content for heading in get_blueprint('executive_summary').sections)}
        elif 'revise one Markdown section' in system:result={'content':'Cedar has 12 beds. Cedar has 18 beds. Conflict: the accounts disagree.'}
        else:result={'passed':True,'issues':[],'violations':[],'failing_claims':[],
                     'reasoning':'Isolated HTTP mock review. This does not establish real-provider semantic accuracy.'}
        text=result if isinstance(result,str) else json.dumps(result)
        data=json.dumps({'id':'msg_phase6_fixture','type':'message','role':'assistant','model':'phase6-local-fixture',
            'content':[{'type':'text','text':text}],'stop_reason':'end_turn','stop_sequence':None,
            'usage':{'input_tokens':10,'output_tokens':20}}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

provider=ThreadingHTTPServer(('127.0.0.1',0),Provider)
threading.Thread(target=provider.serve_forever,daemon=True).start()
os.environ['ANTHROPIC_BASE_URL']=f'http://127.0.0.1:{provider.server_port}'
from api.main import app
from orchestrator.queue import run_forever
worker=None
@app.on_event('startup')
async def start_worker():
    global worker
    worker=asyncio.create_task(run_forever())
@app.on_event('shutdown')
async def stop_worker():
    worker.cancel();await asyncio.gather(worker,return_exceptions=True);provider.shutdown()
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8000)
