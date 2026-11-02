"""Session auth, tenant boundaries, live role changes and immutable version approvals."""
import pytest
from uuid import UUID,uuid4
from httpx import AsyncClient,ASGITransport
from sqlalchemy import select
from api.main import app
from api.dependencies import get_db
from db.models import Source,Generation,Artifact,ArtifactVersion,AuditRecord
from teams.models import Member,Workspace,User,ReviewDecision,SessionToken
from teams.scope import workspace
from schemas.enums import SensitivityLevel,SensitivitySource,GenerationStatus
from revisions.content import digest

PASSWORD='Local-test-password-7!'

@pytest.fixture
async def team_client(session_factory,monkeypatch):
    async def database():
        async with session_factory() as db:
            try:yield db;await db.commit()
            except Exception:await db.rollback();raise
    app.dependency_overrides[get_db]=database
    monkeypatch.setenv('API_KEYS','test-key:administrator:admin')
    monkeypatch.setattr('api.dependencies._API_KEYS',set())
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://testserver',headers={'X-API-Key':'test-key'}) as client:
        yield client
    app.dependency_overrides.clear()

async def setup(c):
    response=await c.post('/api/v1/auth/setup',json={'email':'owner@example.test','password':PASSWORD,'name':'Owner'})
    assert response.status_code==201,response.text
    return response.json()

async def invite(c,email,role):
    response=await c.post('/api/v1/team-invitations',json={'email':email,'role':role})
    assert response.status_code==201,response.text
    return response.json()['token']

async def accept(c,token,email):
    response=await c.post('/api/v1/auth/accept',json={'token':token,'email':email,'name':email,'password':PASSWORD})
    assert response.status_code==201,response.text
    return response.json()

async def seed(factory,space='legacy',owner='owner'):
    t=workspace.set(space)
    try:
        async with factory() as db:
            s=Source(filename='Private.txt',extracted_text='Private exact fact.',sensitivity=SensitivityLevel.PUBLIC,sensitivity_source=SensitivitySource.OPERATOR)
            db.add(s);await db.flush()
            g=Generation(source_id=s.id,output_types=['executive_summary'],params={},status=GenerationStatus.COMPLETED);db.add(g);await db.flush()
            a=Artifact(generation_id=g.id,output_type='executive_summary',content='# Test\nPrivate exact fact.',facts_used=[],review_results=[]);db.add(a);await db.flush()
            v=ArtifactVersion(artifact_id=a.id,owner=owner,label='For approval',origin='original',content=a.content,
                content_hash=digest(a.content),source_hash=digest(s.extracted_text),request_id=str(uuid4()),request_hash='test')
            db.add(v);await db.commit();return s,g,a,v
    finally:workspace.reset(t)

async def test_auth_session_and_last_owner(team_client,session_factory):
    c=team_client;owner=await setup(c)
    assert (await c.get('/api/v1/auth/me')).json()['role']=='owner'
    assert (await c.put('/api/v1/team-members/'+owner['id'],json={'role':'viewer'})).status_code==409
    assert (await c.post('/api/v1/auth/logout')).status_code==200
    assert (await c.get('/api/v1/auth/me')).status_code==401
    assert (await c.post('/api/v1/auth/login',json={'email':'owner@example.test','password':'Wrong-password-123'})).status_code==401
    assert (await c.post('/api/v1/auth/login',json={'email':'owner@example.test','password':PASSWORD})).status_code==200
    assert (await c.post('/api/v1/auth/logout',headers={'Origin':'https://attacker.invalid'})).status_code==403
    async with session_factory() as db:
        user=(await db.execute(select(User))).scalar_one();assert PASSWORD not in user.password_hash
        assert len((await db.execute(select(SessionToken))).scalars().all())==1

async def test_initial_setup_recovers_from_stale_cookie_but_requires_admin_key(team_client):
    c=team_client;c.cookies.set('traceform_session','obsolete-cookie',domain='testserver.local',path='/')
    payload={'email':'owner@example.test','password':PASSWORD,'name':'Owner'}
    denied=await c.post('/api/v1/auth/setup',json=payload,headers={'X-API-Key':'wrong'})
    assert denied.status_code==401
    assert (await c.post('/api/v1/auth/setup',json=payload)).status_code==201
    assert (await c.get('/api/v1/auth/me')).json()['role']=='owner'

async def test_workspace_isolation_every_resource_family(team_client,session_factory):
    c=team_client;owner=await setup(c);s,g,a,v=await seed(session_factory,owner=owner['id'])
    from db.models import SourceCollection,CreationPreset,SynthesisAnalysis,VersionOperation,EvaluationRun
    from teams.models import ReviewRequest,Comment
    async with session_factory() as db:
        collection=SourceCollection(owner=owner['id'],name='Private collection',source_ids=[str(s.id)])
        preset=CreationPreset(owner=owner['id'],name='Private preset',settings={})
        review=ReviewRequest(version_id=v.id,artifact_id=a.id,requester=owner['id'],assignee=owner['id'],content_hash=v.content_hash)
        comment=Comment(version_id=v.id,actor=owner['id'],body='Private comment')
        db.add_all([collection,preset,review,comment,SynthesisAnalysis(generation_id=g.id,owner=owner['id'],manifest_hash='test'),
            VersionOperation(job_id=g.id,version_id=v.id,owner=owner['id'],operation='review',payload={}),
            EvaluationRun(dataset_version='Private evaluation',dataset_size=1)])
        await db.commit()
    second=await c.post('/api/v1/team-workspaces',json={'name':'Other workspace'});assert second.status_code==201
    assert (await c.post('/api/v1/auth/switch',json={'workspace_id':second.json()['id']})).status_code==200
    paths=[f'/sources/{s.id}',f'/sources/{s.id}/text',f'/generations/{g.id}',f'/generations/{g.id}/status',
        f'/artifacts/{a.id}',f'/artifacts/{a.id}/workspace',f'/artifacts/{a.id}/versions/{v.id}',
        f'/team-versions/{v.id}/approval',f'/team-reviews/{review.id}',f'/collections/{collection.id}',f'/source-analyses/{g.id}',
        f'/artifacts/{a.id}/review-context',f'/artifacts/{a.id}/versions',f'/artifacts/{a.id}/version-tasks',
        f'/artifacts/{a.id}/compare?left=original&right={v.id}',f'/generations/{g.id}/artifacts/executive_summary']
    paths += [f'/artifacts/{a.id}/export?format={fmt}&target={target}&version_id={v.id}&expected_hash={digest(a.content)}'
        for fmt in ['md','txt','docx','pdf','pptx'] for target in ['original','version']]
    for path in paths:
        response=await c.get('/api/v1'+path);assert response.status_code==404,(path,response.text)
        assert 'Private exact fact' not in response.text
    assert (await c.get('/api/v1/sources/')).json()==[]
    assert (await c.get('/api/v1/generations/')).json()==[]
    assert (await c.get('/api/v1/generations/history/list')).json()['total']==0
    for route in ['/presets/','/collections','/source-analyses','/evaluations/history']:
        assert (await c.get('/api/v1'+route)).json()==[],route
    assert (await c.get('/api/v1/evaluations/latest')).json() is None
    assert (await c.get('/api/v1/team-reviews',params={'mine':False,'status':'all'})).json()['total']==0
    events=(await c.get('/api/v1/team-activity')).json()['items']
    assert len(events)==1 and events[0]['action']=='WORKSPACE_CREATED'
    assert events[0]['resource_id']==second.json()['id']
    trail=(await c.get('/api/v1/audit/trail')).json()
    assert len(trail)==1 and trail[0]['event_type']=='WORKSPACE_CREATED'
    metrics=(await c.get('/api/v1/metrics')).json();assert metrics['total_artifacts']==0,metrics
    assert (await c.get('/api/v1/team-comments',params={'version_id':str(v.id)})).status_code==404
    assert (await c.put(f'/api/v1/artifacts/{a.id}/draft',json={'content':'Cross-space edit',
        'expected_revision':0,'base_hash':digest(a.content),'request_id':str(uuid4())})).status_code==404
    assert (await c.post('/api/v1/auth/switch',json={'workspace_id':'nonmember'})).status_code==404
    assert (await c.post('/api/v1/generations/',json={'source_id':str(s.id),'output_types':['executive_summary']})).status_code==404
    writes=[('DELETE',f'/sources/{s.id}',None),('POST',f'/sources/{s.id}/restore',None),
        ('POST',f'/generations/{g.id}/cancel',None),('POST',f'/generations/{g.id}/retry',None),
        ('POST',f'/generations/{g.id}/regenerate?output_type=executive_summary',None),
        ('POST',f'/artifacts/{a.id}/versions',{'source':'original','request_id':str(uuid4())}),
        ('POST',f'/artifacts/{a.id}/versions/{v.id}/restore',{'expected_revision':0,'request_id':str(uuid4())}),
        ('POST',f'/artifacts/{a.id}/versions/{v.id}/tasks',{'operation':'review','budget_ceiling':10000,'request_id':str(uuid4())}),
        ('POST',f'/artifacts/{a.id}/version-tasks/{g.id}/cancel',None),
        ('POST',f'/artifacts/{a.id}/feedback',{'rating':'positive'}),
        ('POST',f'/artifacts/{a.id}/compliance-override',{'reason':'This is a cross-workspace attempt.'}),
        ('POST',f'/source-analyses/{g.id}/cancel',None),('POST',f'/collections/{collection.id}/archive',None),
        ('POST',f'/collections/{collection.id}/restore',None),
        ('PUT',f'/collections/{collection.id}',{'name':'Changed','source_ids':[str(s.id)],'expected_revision':1}),
        ('DELETE',f'/presets/{preset.id}',None),
        ('POST',f'/team-reviews/{review.id}/decision',{'decision':'approved','reason':'Forbidden.','expected_revision':1}),
        ('PUT',f'/team-comments/{comment.id}/resolve',None),
        ('POST','/team-comments',{'version_id':str(v.id),'body':'Forbidden.'}),
        ('POST','/team-reviews',{'version_id':str(v.id),'assignee':owner['id']})]
    for method,path,body in writes:
        response=await c.request(method,'/api/v1'+path,json=body)
        assert response.status_code==404,(method,path,response.text)

async def test_review_assignment_comments_and_new_version_requires_approval(team_client,session_factory):
    c=team_client;owner=await setup(c);s,g,a,v=await seed(session_factory,owner=owner['id'])
    owner_cookie=c.cookies.get('traceform_session')
    token=await invite(c,'reviewer@example.test','reviewer')
    reviewer=await accept(c,token,'reviewer@example.test');reviewer_cookie=c.cookies.get('traceform_session')
    assert (await c.post('/api/v1/sources/',data={'text':'Forbidden','sensitivity':'public'})).status_code==403
    assert (await c.post('/api/v1/team-invitations',json={'email':'x@example.test','role':'editor'})).status_code==403
    c.cookies.set('traceform_session',owner_cookie,domain='testserver.local',path='/')
    requested=await c.post('/api/v1/team-reviews',json={'version_id':str(v.id),'assignee':reviewer['id']});assert requested.status_code==201,requested.text
    rid=requested.json()['id']
    c.cookies.set('traceform_session',reviewer_cookie,domain='testserver.local',path='/')
    assert (await c.get('/api/v1/team-reviews')).json()['total']==1
    assert (await c.get('/api/v1/artifacts/'+str(a.id)+'/versions/'+str(v.id))).status_code==200
    comment=await c.post('/api/v1/team-comments',json={'version_id':str(v.id),'body':'Check this figure.'});assert comment.status_code==201
    reply=await c.post('/api/v1/team-comments',json={'version_id':str(v.id),'body':'Confirmed.','parent_id':comment.json()['id']});assert reply.status_code==201
    assert (await c.put('/api/v1/team-comments/'+comment.json()['id']+'/resolve')).status_code==200
    data={'decision':'approved','reason':'Checked the exact saved version.','expected_revision':1}
    assert (await c.post(f'/api/v1/team-reviews/{rid}/decision',json=data)).status_code==200
    assert (await c.post(f'/api/v1/team-reviews/{rid}/decision',json=data)).status_code==409
    assert (await c.get(f'/api/v1/team-versions/{v.id}/approval')).json()['status']=='approved'
    c.cookies.set('traceform_session',owner_cookie,domain='testserver.local',path='/')
    saved=await c.post(f'/api/v1/artifacts/{a.id}/versions',json={'source':'import','content':'Edited text','label':'Changed','request_id':str(uuid4())})
    assert saved.status_code==201,saved.text
    assert (await c.get('/api/v1/team-versions/'+saved.json()['id']+'/approval')).json()['status']=='unapproved'
    activity=(await c.get('/api/v1/team-activity',params={'action':'VERSION_APPROVED'})).json()
    assert activity['total']==1 and activity['items'][0]['details']['version_id']==str(v.id)
    # Role removal takes effect on the very next request, even with an existing cookie.
    assert (await c.delete('/api/v1/team-members/'+reviewer['id'])).status_code==200
    c.cookies.set('traceform_session',reviewer_cookie,domain='testserver.local',path='/')
    assert (await c.get('/api/v1/team-reviews')).status_code==401

async def test_invitation_email_revocation_and_single_use(team_client):
    c=team_client;await setup(c);owner_cookie=c.cookies.get('traceform_session')
    token=await invite(c,'viewer@example.test','viewer')
    bad=await c.post('/api/v1/auth/accept',json={'token':token,'email':'other@example.test','password':PASSWORD})
    assert bad.status_code==403
    await accept(c,token,'viewer@example.test')
    assert (await c.post('/api/v1/team-comments',json={'version_id':str(uuid4()),'body':'No'})).status_code==403
    c.cookies.set('traceform_session',owner_cookie,domain='testserver.local',path='/')
    assert (await c.post('/api/v1/auth/accept',json={'token':token,'email':'viewer@example.test','password':PASSWORD})).status_code==410

async def test_membership_downgrade_live_and_no_cross_space_review(team_client,session_factory):
    c=team_client;owner=await setup(c);_,_,a,v=await seed(session_factory,owner=owner['id'])
    owner_cookie=c.cookies.get('traceform_session');token=await invite(c,'editor@example.test','editor')
    user=await accept(c,token,'editor@example.test');cookie=c.cookies.get('traceform_session')
    assert (await c.post('/api/v1/team-reviews',json={'version_id':str(v.id),'assignee':user['id']})).status_code==422
    c.cookies.set('traceform_session',owner_cookie,domain='testserver.local',path='/')
    assert (await c.put('/api/v1/team-members/'+user['id'],json={'role':'viewer'})).status_code==200
    c.cookies.set('traceform_session',cookie,domain='testserver.local',path='/')
    assert (await c.get('/api/v1/auth/me')).json()['role']=='viewer'
    assert (await c.post('/api/v1/artifacts/'+str(a.id)+'/versions',json={'source':'original','request_id':str(uuid4())})).status_code==403
    assert (await c.get(f'/api/v1/artifacts/{a.id}/export',params={'format':'md','target':'version','version_id':str(v.id),'expected_hash':v.content_hash})).status_code==200

async def test_expired_invitation_and_session(team_client,session_factory):
    from teams.models import Invitation
    from orchestrator.runtime import utcnow
    from datetime import timedelta
    c=team_client;await setup(c);token=await invite(c,'expired@example.test','viewer')
    async with session_factory() as db:
        row=(await db.execute(select(Invitation))).scalar_one();row.expires_at=utcnow()-timedelta(seconds=1)
        await db.commit()
    assert (await c.post('/api/v1/auth/accept',json={'token':token,'email':'expired@example.test','password':PASSWORD})).status_code==410
    async with session_factory() as db:
        row=(await db.execute(select(SessionToken))).scalar_one();row.expires_at=utcnow()-timedelta(seconds=1);await db.commit()
    assert (await c.get('/api/v1/sources/')).status_code==401

async def test_worker_inherits_tenant_for_new_artifacts(team_client,session_factory,monkeypatch):
    from tests.test_multiple_sources import provider
    from db.models import DurableJob
    from orchestrator.queue import run_once
    c=team_client;await setup(c)
    space=(await c.post('/api/v1/team-workspaces',json={'name':'Worker isolation'})).json()['id']
    assert (await c.post('/api/v1/auth/switch',json={'workspace_id':space})).status_code==200
    s,_,_,_=await seed(session_factory,space)
    async def local(*args,**kwargs):return {'available':True,'model':'test-model','message':'Local test'}
    monkeypatch.setattr('agents.availability.provider_health',local)
    payload={'source_id':str(s.id),'output_types':['executive_summary'],'budget_ceiling':100000}
    r=await c.post('/api/v1/generations/',json=payload);assert r.status_code==202,r.text
    async def pipeline(task,gid):
        async with session_factory() as db:
            gen=await db.get(Generation,UUID(gid));assert gen.workspace_id==space
            db.add(Artifact(generation_id=gen.id,output_type='executive_summary',content='Tenant output',facts_used=[],review_results=[]))
            gen.status=GenerationStatus.COMPLETED;await db.commit()
    assert await run_once(factory=session_factory,pipeline=pipeline)
    async with session_factory() as db:
        a=(await db.execute(select(Artifact).where(Artifact.generation_id==UUID(r.json()['id'])))).scalar_one()
        assert a.workspace_id==space
    await c.post('/api/v1/auth/switch',json={'workspace_id':'legacy'})
    assert (await c.get('/api/v1/artifacts/'+str(a.id))).status_code==404

async def test_concurrent_owner_demotions_keep_an_owner(team_client,session_factory):
    import asyncio
    from teams.scope import identity
    from api.routes.teams import change_member,RoleWrite
    c=team_client;first=await setup(c);token=await invite(c,'second-owner@example.test','editor')
    second=await accept(c,token,'second-owner@example.test')
    async with session_factory() as db:
        member=await db.get(Member,('legacy',second['id']));member.role='owner';await db.commit()
    async def demote(user_id):
        t=workspace.set('legacy');u=identity.set({'user_id':user_id,'workspace_id':'legacy','role':'owner'})
        try:
            async with session_factory() as db:
                try:return await change_member(user_id,RoleWrite(role='viewer'),db)
                except Exception as exc:
                    await db.rollback();return getattr(exc,'status_code',str(exc))
        finally:identity.reset(u);workspace.reset(t)
    result=await asyncio.gather(demote(first['id']),demote(second['id']))
    assert sum(isinstance(r,dict) for r in result)==1,result
    assert 409 in result,result
    async with session_factory() as db:
        members=(await db.execute(select(Member).where(Member.space_id=='legacy',Member.role=='owner'))).scalars().all()
        assert len(members)==1

async def test_decisions_and_audit_rows_are_immutable(team_client,session_factory):
    c=team_client;owner=await setup(c);_,_,_,v=await seed(session_factory,owner=owner['id'])
    r=await c.post('/api/v1/team-reviews',json={'version_id':str(v.id),'assignee':owner['id']})
    assert r.status_code==201
    decision=await c.post('/api/v1/team-reviews/'+r.json()['id']+'/decision',json={'decision':'approved','reason':'Exact version checked.','expected_revision':1})
    assert decision.status_code==200
    for model,field in [(ReviewDecision,'reason'),(AuditRecord,'event_type')]:
        async with session_factory() as db:
            row=(await db.execute(select(model).limit(1))).scalar_one();setattr(row,field,'rewritten')
            with pytest.raises(ValueError,match='immutable'):await db.commit()
            await db.rollback()

async def test_authenticated_workspace_generation_uses_full_pipeline(team_client,session_factory,monkeypatch):
    from tests.test_multiple_sources import provider
    from db.models import LLMCall,KnowledgeExtractionModel
    from orchestrator.queue import run_once
    c=team_client;await setup(c)
    space=(await c.post('/api/v1/team-workspaces',json={'name':'Pipeline workspace'})).json()['id']
    await c.post('/api/v1/auth/switch',json={'workspace_id':space})
    uploaded=await c.post('/api/v1/sources/',data={'text':'Cedar has 12 beds. Cedar opened in 2026.','sensitivity':'public'})
    assert uploaded.status_code==201,uploaded.text
    async with session_factory() as db:source=await db.get(Source,UUID(uploaded.json()['id']))
    provider(monkeypatch,[source])
    async def available(configuration=None):return {'available':True,'model':'test-model','message':'Fixture ready'}
    monkeypatch.setattr('agents.availability.provider_health',available)
    submitted=await c.post('/api/v1/generations/',json={'source_id':str(source.id),'output_types':['executive_summary'],'budget_ceiling':200000})
    assert submitted.status_code==202,submitted.text
    assert await run_once(factory=session_factory)
    completed=(await c.get('/api/v1/generations/'+submitted.json()['id'])).json()
    assert completed['status']=='completed',completed
    assert completed['artifacts'],completed
    async with session_factory() as db:
        for model in [Artifact,LLMCall,KnowledgeExtractionModel]:
            rows=(await db.execute(select(model))).scalars().all()
            assert rows and all(row.workspace_id==space for row in rows),model.__name__
