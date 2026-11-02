"""Isolated browser acceptance fixture: synthetic identities/data; no external provider calls."""
import asyncio,os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'traceform'))
from cryptography.fernet import Fernet
runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
key=runtime/'phase8-ui-master-key'
if not key.exists():key.write_bytes(Fernet.generate_key())
os.environ.update(APP_ENV='test',DATABASE_URL='sqlite+aiosqlite:///'+str(runtime/'phase8-ui.db'),
    OBJECT_STORAGE_PATH=str(runtime/'phase8-ui-storage'),API_KEYS='phase8-fixture-admin-key:fixture:admin',
    TRACEFORM_MASTER_KEY=key.read_text().strip(),GEMINI_API_KEY='',ANTHROPIC_API_KEY='fixture-only',
    ANTHROPIC_BASE_URL='http://127.0.0.1:9',TRACEFORM_AUTO_MIGRATE='true')
from db.session import engine,AsyncSessionLocal
from db.migrate import migrate
from db.models import Source,Generation,Artifact,ArtifactVersion,AuditRecord,LLMCall
from teams.models import User,Workspace,Member,ReviewRequest
from teams.auth import password
from teams.scope import workspace
from schemas.enums import SensitivityLevel,SensitivitySource,GenerationStatus
from revisions.content import digest
from sqlalchemy import select
from uuid import uuid4

async def seed():
    await migrate(engine)
    async with AsyncSessionLocal() as db:
        if not await db.scalar(select(User.id).limit(1)):
            db.add(Workspace(id='legacy',name='Cedar research'));db.add(Workspace(id='separate-fixture',name='Separate workspace'))
            users=[]
            for role,name in [('owner','Alex Owner'),('editor','Sam Editor'),('reviewer','Riley Reviewer'),('viewer','Casey Viewer')]:
                u=User(email=role+'@phase8.test',name=name,password_hash=password('Phase8-fixture-password!'))
                db.add(u);await db.flush();users.append(u);db.add(Member(space_id='legacy',user_id=u.id,role=role))
            db.add(Member(space_id='separate-fixture',user_id=users[0].id,role='owner'))
            source=Source(filename='Cedar_Research.txt',extracted_text='Cedar has 12 raised beds. Volunteers meet every Saturday at 9 AM.',sensitivity=SensitivityLevel.INTERNAL,sensitivity_source=SensitivitySource.OPERATOR)
            db.add(source);await db.flush()
            gen=Generation(source_id=source.id,params={},output_types=['executive_summary'],status=GenerationStatus.COMPLETED)
            db.add(gen);await db.flush()
            content='## Executive Summary\nCedar has 12 raised beds.\n\n## Decision Required\nProposal: confirm the next volunteer session.'
            artifact=Artifact(generation_id=gen.id,output_type='executive_summary',content=content,facts_used=[],review_results=[])
            db.add(artifact);await db.flush()
            version=ArtifactVersion(artifact_id=artifact.id,owner=users[1].id,label='Cedar briefing — ready for review',origin='original',content=content,content_hash=digest(content),source_hash=digest(source.extracted_text),request_id=str(uuid4()),request_hash='fixture')
            db.add(version);await db.flush()
            review=ReviewRequest(version_id=version.id,artifact_id=artifact.id,requester=users[1].id,assignee=users[2].id,content_hash=version.content_hash)
            db.add(review);await db.flush()
            db.add(AuditRecord(event_type='REVIEW_ASSIGNED',operator_id=users[1].id,resource_id=str(artifact.id),metadata_json={'version_id':str(version.id),'review_id':str(review.id)}))
            from datetime import datetime,timedelta,timezone
            start=datetime.now(timezone.utc)-timedelta(hours=1)
            for state,duration,usage in [('succeeded',2,{'input_tokens':120,'output_tokens':40,'estimated_cost_usd':.00024,'usage_recorded':True}),('failed',5,None),('uncertain',3,None)]:
                db.add(LLMCall(generation_id=gen.id,fingerprint=str(uuid4()),model='synthetic-acceptance-model',provider='fixture',stage='browser acceptance',pricing={},reservation=0,status=state,created_at=start,finished_at=start+timedelta(seconds=duration),usage=usage,error='Synthetic unavailable response.' if state=='failed' else None))
            await db.commit()
            (runtime/'phase8-ui-fixture.json').write_text(json.dumps({'artifact_id':str(artifact.id),'version_id':str(version.id),'review_id':str(review.id)}))
    await engine.dispose()
asyncio.run(seed())
from api.main import app
@app.on_event('startup')
async def fixture_worker():
    from orchestrator.queue import run_forever
    app.state.fixture_worker=asyncio.create_task(run_forever())
@app.on_event('shutdown')
async def stop_fixture_worker():
    app.state.fixture_worker.cancel()
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8000)
