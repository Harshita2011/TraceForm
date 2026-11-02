"""Measured numerators/denominators, durable execution and complete recovery evidence."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID,uuid4
import json
import pytest
from sqlalchemy import select
from db.models import Source,Generation,Artifact,ArtifactVersion,LLMCall,DurableJob,ProviderConfiguration,AuditRecord
from tests.test_version_workspace import seed,snapshot
from eval.models import BenchmarkDataset,BenchmarkCase,BenchmarkOutcome

async def dataset(client,db):
    a,s=await seed(db)
    saved=await snapshot(client,a,source='import',content='Acme Corp launched Widget X. It cost $99.')
    payload={'name':'Release evidence','version':'v1','cases':[{'title':'Two factual claims','version_id':saved['id'],
        'complete_claim_inventory':True,'style_passed':False,'style_notes':'Required headings are missing.',
        'claims':[{'claim':'Acme Corp launched Widget X.','verdict':'supported','reason':'Exact source statement.',
            'source_span':'Acme Corp launched Widget X.'},{'claim':'It cost $99.','verdict':'unsupported','reason':'No cost is stated in the source.'}]}]}
    response=await client.post('/api/v1/evaluations/datasets',json=payload)
    assert response.status_code==201,response.text
    return response.json(),payload,a,s

async def test_durable_measurements_recompute_from_saved_evidence(client,db_session,session_factory,monkeypatch):
    d,payload,a,s=await dataset(client,db_session)
    async def forbidden(*args,**kwargs):raise AssertionError('Scoring human annotations must not call providers.')
    monkeypatch.setattr('agents.llm._call_llm_impl',forbidden)
    body={'dataset_id':d['id'],'request_id':str(uuid4())}
    first=await client.post('/api/v1/evaluations/execute',json=body);assert first.status_code==202,first.text
    assert (await client.post('/api/v1/evaluations/execute',json=body)).json()==first.json()
    from orchestrator.queue import run_once
    assert await run_once(factory=session_factory)
    result=(await client.get('/api/v1/evaluations/executions/'+first.json()['id'])).json()
    assert result['status']=='completed',result
    assert result['metrics']['fact_accuracy']==.5
    assert result['metrics']['hallucination_rate']==.5
    assert result['metrics']['citation_coverage']==0
    assert result['metrics']['style_adherence_rate']==0
    assert result['metrics']['claim_count']==2 and result['metrics']['style_denominator']==1
    assert result['recomputation_matches'] is True
    assert result['cases'][0]['annotations']['claims'][1]['reason']=='No cost is stated in the source.'
    # Existing generation list stays focused on user outputs.
    assert all(g['id']!=first.json()['id'] for g in (await client.get('/api/v1/generations/')).json())
    assert (await client.post('/api/v1/evaluations/datasets',json=payload)).status_code==409

async def test_partial_and_uncertain_assessments_never_invent_accuracy(client,db_session,session_factory):
    _,payload,_,_=await dataset(client,db_session)
    payload['version']='partial';payload['cases'][0]['complete_claim_inventory']=False
    d=(await client.post('/api/v1/evaluations/datasets',json=payload)).json()
    r=(await client.post('/api/v1/evaluations/execute',json={'dataset_id':d['id'],'request_id':str(uuid4())})).json()
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    m=(await client.get('/api/v1/evaluations/executions/'+r['id'])).json()['metrics']
    assert m['fact_accuracy'] is None and m['hallucination_rate'] is None
    assert m['style_adherence_rate']==0 and m['claim_count']==2

async def test_changed_source_records_failed_case_without_old_content(client,db_session,session_factory):
    d,_,_,s=await dataset(client,db_session)
    s.extracted_text='Changed source.';await db_session.commit()
    r=await client.post('/api/v1/evaluations/execute',json={'dataset_id':d['id'],'request_id':str(uuid4())})
    assert r.status_code==202,r.text
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    result=(await client.get('/api/v1/evaluations/executions/'+r.json()['id'])).json()
    assert result['metrics']['failed_cases']==1 and result['metrics']['fact_accuracy'] is None
    assert result['cases'][0]['content'] is None and result['cases'][0]['annotations'] is None

async def test_dataset_validates_quotes_and_claims(client,db_session):
    _,payload,_,_=await dataset(client,db_session)
    payload['version']='bad';payload['cases'][0]['claims'][0]['source_span']='Invented quote'
    assert (await client.post('/api/v1/evaluations/datasets',json=payload)).status_code==422
    payload['cases'][0]['claims'][0]['source_span']='Acme Corp launched Widget X.'
    payload['cases'][0]['claims'][0]['claim']='Not in the output'
    assert (await client.post('/api/v1/evaluations/datasets',json=payload)).status_code==422

async def test_operations_use_recorded_timings_and_known_usage(client,db_session):
    a,_=await seed(db_session);now=datetime.now(timezone.utc)-timedelta(hours=1)
    for status,seconds,usage in [('succeeded',2,{'input_tokens':3,'output_tokens':4,'estimated_cost_usd':.012,'usage_recorded':True}),('uncertain',4,None)]:
        db_session.add(LLMCall(generation_id=a.generation_id,fingerprint=str(uuid4()),model='measured-model',provider='fixture',pricing={},reservation=0,
            status=status,stage='test',created_at=now,finished_at=now+timedelta(seconds=seconds),usage=usage))
    await db_session.commit()
    response=await client.get('/api/v1/operations/summary',params={'since':(now-timedelta(hours=1)).isoformat(),'until':(now+timedelta(hours=1)).isoformat()})
    assert response.status_code==200,response.text
    m=response.json();assert m['tokens']==7 and m['estimated_cost_usd']==.012
    assert m['unknown_usage_requests']==1 and m['provider_requests']==2
    assert m['call_latency']['p50_ms']==3000 and m['call_latency']['samples']==2
    assert m['job_latency']['p50_ms'] is None
    assert (await client.get('/api/v1/operations/requests',params={'status':'uncertain'})).json()['total']==1
    assert (await client.get('/api/v1/operations/summary',params={'since':now.isoformat(),'until':(now-timedelta(days=1)).isoformat()})).status_code==422

async def test_request_logs_do_not_capture_query_secrets(client,monkeypatch,caplog):
    from operations_logging import log
    monkeypatch.setattr(log,'propagate',True)
    with caplog.at_level('INFO',logger='traceform.requests'):
        r=await client.get('/api/v1/healthz?token=private-query-marker',headers={'X-Request-ID':'release-check-123'})
    assert r.headers['X-Request-ID']=='release-check-123'
    events=[json.loads(r.message) for r in caplog.records if r.name=='traceform.requests']
    assert events and events[-1]['route'] in {'/api/v1/healthz','/healthz'}
    assert 'private-query-marker' not in json.dumps(events)

async def test_encrypted_backup_restores_business_rows_files_and_credentials(test_engine,session_factory,tmp_path,monkeypatch):
    from db.migrate import migrate
    from recovery import backup,restore,read_bundle
    from cryptography.fernet import Fernet
    from teams.models import User,Workspace,Member,ReviewRequest,ReviewDecision,Comment
    from teams.auth import password,matches
    from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
    await migrate(test_engine)
    storage=tmp_path/'storage';storage.mkdir();(storage/'source.txt').write_text('Private exact fact.')
    master=tmp_path/'master';master.write_bytes(Fernet.generate_key());vault=tmp_path/'vault';vault.write_bytes(Fernet.generate_key())
    async with session_factory() as db:
        from tests.test_teams import seed as team_seed
    s,g,a,v=await team_seed(session_factory)
    async with session_factory() as db:
        source=await db.get(Source,s.id);source.raw_content_ref='source.txt'
        u=User(email='restore@example.test',name='Restore owner',password_hash=password('Restore-fixture-password!'))
        db.add(Workspace(id='legacy',name='Restore workspace'));db.add(u);await db.flush();db.add(Member(space_id='legacy',user_id=u.id,role='owner'))
        review=ReviewRequest(version_id=v.id,artifact_id=a.id,requester=u.id,assignee=u.id,content_hash=v.content_hash,status='approved');db.add(review);await db.flush()
        db.add(ReviewDecision(review_id=review.id,version_id=v.id,content_hash=v.content_hash,actor=u.id,decision='approved',reason='Restore fixture.'))
        db.add(Comment(version_id=v.id,actor=u.id,body='Preserved discussion.'))
        db.add(ProviderConfiguration(provider='fixture',model='fixture-model',encrypted_key=Fernet(master.read_bytes()).encrypt(b'restored-provider-secret').decode(),pricing={},created_by=u.id))
        from db.models import ArtifactDraft
        db.add(ArtifactDraft(artifact_id=a.id,owner=u.id,content='Preserved working draft.',revision=1,base_hash=v.content_hash,last_request_id=str(uuid4()),request_hash='fixture'))
        await db.commit()
    output=tmp_path/'backup.tfbackup'
    original_url=test_engine.url.render_as_string(hide_password=False)
    saved=await backup(original_url,storage,master,output,vault,True)
    assert b'Private exact fact' not in output.read_bytes()
    parsed,entries=read_bundle(output,vault);assert parsed['counts']['artifact_versions']==1
    if test_engine.dialect.name=='postgresql':
        name='traceform_test_restore_'+uuid4().hex[:12]
        async with test_engine.connect() as conn:
            conn=await conn.execution_options(isolation_level='AUTOCOMMIT');await conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
        target_url=test_engine.url.set(database=name).render_as_string(hide_password=False)
    else:target_url='sqlite+aiosqlite:///'+str(tmp_path/'restored.db')
    target_storage=tmp_path/'restored-storage'
    recovered=await restore(output,vault,target_url,target_storage,True)
    assert recovered['verified'] and recovered['counts']==saved['counts']
    target=create_async_engine(target_url);factory=async_sessionmaker(target,expire_on_commit=False)
    try:
        async with factory() as db:
            user=(await db.execute(select(User))).scalar_one();assert matches('Restore-fixture-password!',user.password_hash)
            assert (await db.get(ArtifactVersion,v.id)).content==v.content
            assert (await db.execute(select(ReviewDecision))).scalar_one().content_hash==v.content_hash
            config=(await db.execute(select(ProviderConfiguration))).scalar_one()
            assert Fernet((target_storage/'.provider-master-key').read_bytes()).decrypt(config.encrypted_key.encode())==b'restored-provider-secret'
        # Exercise the restored instance through authenticated APIs, not just row counts.
        from httpx import AsyncClient,ASGITransport
        from api.main import app
        from api.dependencies import get_db
        async def restored_database():
            async with factory() as db:
                yield db
        app.dependency_overrides[get_db]=restored_database
        try:
            async with AsyncClient(transport=ASGITransport(app=app),base_url='http://testserver') as client:
                login=await client.post('/api/v1/auth/login',json={'email':'restore@example.test','password':'Restore-fixture-password!'})
                assert login.status_code==200,login.text
                result=await client.get(f'/api/v1/artifacts/{a.id}/versions/{v.id}')
                assert result.status_code==200 and result.json()['content']==v.content
                result=await client.get(f'/api/v1/artifacts/{a.id}/workspace')
                assert result.status_code==200 and result.json()['draft']['content']=='Preserved working draft.'
                result=await client.get('/api/v1/team-comments',params={'version_id':str(v.id)})
                assert result.status_code==200 and 'Preserved discussion.' in result.text
                result=await client.get('/api/v1/team-reviews',params={'mine':False,'status':'all'})
                assert result.status_code==200 and 'approved' in result.text
                result=await client.get(f'/api/v1/artifacts/{a.id}/export',params={'format':'txt','target':'version','version_id':str(v.id),'expected_hash':v.content_hash})
                assert result.status_code==200 and 'Private exact fact.' in result.text
        finally:app.dependency_overrides.clear()
        assert (target_storage/'source.txt').read_text()=='Private exact fact.'
        with pytest.raises(ValueError,match='empty|existing|new'):await restore(output,vault,target_url,target_storage,True)
    finally:
        await target.dispose()
        if test_engine.dialect.name=='postgresql':
            async with test_engine.connect() as conn:
                conn=await conn.execution_options(isolation_level='AUTOCOMMIT');await conn.exec_driver_sql(f'DROP DATABASE "{name}"')


from tests.test_teams import team_client

async def test_benchmarks_and_operations_enforce_workspace_and_readonly_roles(team_client,session_factory):
    from tests.test_teams import setup,seed as team_seed,invite,accept
    c=team_client;owner=await setup(c)
    _,g,_,v=await team_seed(session_factory,owner=owner['id'])
    payload={'name':'Tenant benchmark','version':'v1','cases':[{'title':'Private case','version_id':str(v.id),
        'claims':[{'claim':'Private exact fact.','verdict':'supported','reason':'Direct statement.', 'source_span':'Private exact fact.'}]}]}
    d=await c.post('/api/v1/evaluations/datasets',json=payload);assert d.status_code==201,d.text
    did=d.json()['id']
    eid=(await c.post('/api/v1/evaluations/execute',json={'dataset_id':did,'request_id':str(uuid4())})).json()['id']
    viewer=await invite(c,'viewer@example.test','viewer')
    other=await c.post('/api/v1/team-workspaces',json={'name':'Separate team'});assert other.status_code==201,other.text
    assert (await c.post('/api/v1/auth/switch',json={'workspace_id':other.json()['id']})).status_code==200
    for path in [f'/evaluations/datasets/{did}',f'/evaluations/executions/{eid}']:
        assert (await c.get('/api/v1'+path)).status_code==404
    for path in ['/evaluations/datasets','/evaluations/executions','/operations/requests']:
        assert (await c.get('/api/v1'+path)).json()['total']==0
    assert (await c.get('/api/v1/operations/summary')).json()['admitted_jobs']==0
    assert (await c.post('/api/v1/evaluations/execute',json={'dataset_id':did,'request_id':str(uuid4())})).status_code==404
    assert (await c.post(f'/api/v1/evaluations/executions/{eid}/cancel')).status_code==404
    await c.post('/api/v1/auth/logout');await accept(c,viewer,'viewer@example.test')
    assert (await c.get('/api/v1/evaluations/datasets/'+did)).status_code==200
    assert (await c.post('/api/v1/evaluations/datasets',json=payload)).status_code==403
    assert (await c.post('/api/v1/evaluations/execute',json={'dataset_id':did,'request_id':str(uuid4())})).status_code==403
    assert (await c.post(f'/api/v1/evaluations/executions/{eid}/cancel')).status_code==403

async def test_benchmark_cancel_is_durable_without_provider_calls(client,db_session,session_factory):
    d,_,_,_=await dataset(client,db_session)
    r=await client.post('/api/v1/evaluations/execute',json={'dataset_id':d['id'],'request_id':str(uuid4())})
    eid=r.json()['id']
    assert (await client.post(f'/api/v1/evaluations/executions/{eid}/cancel')).status_code==200
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    result=(await client.get('/api/v1/evaluations/executions/'+eid)).json()
    assert result['status']=='cancelled' and not result['can_cancel']
    assert result['recomputed_metrics']['pending_cases']==1


async def test_legacy_benchmark_evidence_is_operator_private(client,db_session,monkeypatch):
    d,_,_,_=await dataset(client,db_session)
    eid=(await client.post('/api/v1/evaluations/execute',json={'dataset_id':d['id'],'request_id':str(uuid4())})).json()['id']
    monkeypatch.setenv('API_KEYS','test-key,other-legacy-key')
    monkeypatch.setattr('api.dependencies._API_KEYS',set())
    headers={'X-API-Key':'other-legacy-key'}
    for path in ['/datasets/'+d['id'],'/executions/'+eid]:
        assert (await client.get('/api/v1/evaluations'+path,headers=headers)).status_code==404
    for path in ['/datasets','/executions']:
        assert (await client.get('/api/v1/evaluations'+path,headers=headers)).json()['total']==0
    assert (await client.post('/api/v1/evaluations/execute',headers=headers,json={'dataset_id':d['id'],'request_id':str(uuid4())})).status_code==404


def test_executive_review_uses_canonical_sections_without_treating_markdown_as_social():
    from agents.generators.blueprints import get_blueprint
    from agents.reviewers.specialist import review_executive_summary
    bp=get_blueprint('executive_summary')
    content='\n\n'.join('## '+title+'\nThere are 12 raised beds.' for title in bp.sections)
    result=review_executive_summary(content,bp)
    assert result.passed and result.anti_bleed_passed
    assert not review_executive_summary(content+'\n#Garden',bp).passed


async def test_evaluation_resumes_committed_case_after_worker_interruption(client,db_session,session_factory):
    d,_,_,_=await dataset(client,db_session)
    eid=UUID((await client.post('/api/v1/evaluations/execute',json={'dataset_id':d['id'],'request_id':str(uuid4())})).json()['id'])
    from eval.measured import counts
    from orchestrator.runtime import utcnow
    case=await db_session.scalar(select(BenchmarkCase).where(BenchmarkCase.dataset_id==UUID(d['id'])))
    db_session.add(BenchmarkOutcome(execution_id=eid,case_id=case.id,status='measured',counts=counts(case)))
    job=await db_session.get(DurableJob,eid)
    job.status='running';job.attempts=1;job.lease_token='interrupted';job.lease_until=utcnow()-timedelta(seconds=1)
    await db_session.commit()
    from orchestrator.queue import run_once
    assert await run_once(factory=session_factory)
    result=(await client.get('/api/v1/evaluations/executions/'+str(eid))).json()
    assert result['status']=='completed' and result['recomputation_matches']
    assert result['metrics']['measured_cases']==1
    async with session_factory() as db:
        outcomes=(await db.execute(select(BenchmarkOutcome).where(BenchmarkOutcome.execution_id==eid))).scalars().all()
        assert len(outcomes)==1 and (await db.get(DurableJob,eid)).attempts==2
