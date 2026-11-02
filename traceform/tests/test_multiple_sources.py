"""Cross-document provenance, explicit conflicts, isolated collections and snapshot safety."""
import json
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,func,update
from db.models import Source,Generation,Artifact,GenerationDocument,KnowledgeExtractionModel,SourceCollection,LLMCall
from schemas.enums import SensitivityLevel,SensitivitySource
from synthesis.context import load_context
from evidence.validation import validate_evidence,version,anchor


async def seed(db):
    result=[]
    for name,count in [('First source.txt',12),('Second source.txt',18)]:
        row=Source(filename=name,extracted_text=f'Cedar has {count} beds. Cedar opened in 2026.',
                   sensitivity=SensitivityLevel.PUBLIC,sensitivity_source=SensitivitySource.OPERATOR)
        db.add(row);result.append(row)
    await db.commit()
    return result


def provider(monkeypatch,sources):
    from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION
    from agents.generators.blueprints import get_blueprint
    async def invoke(client,model,system_prompt,user_content,*args,**kwargs):
        if 'Knowledge Extraction analyst' in system_prompt:
            source=next(s for s in sources if s.extracted_text in user_content)
            data=MINIMAL_EXTRACTION.model_dump(mode='json');data['facts']=[]
            for claim in [source.extracted_text.split('. ')[0]+'.','Cedar opened in 2026.']:
                start=source.extracted_text.index(claim)
                data['facts'].append({'claim':claim,'source_span':claim,'start_char':start,'end_char':start+len(claim),'confidence':1})
        elif 'compare source facts' in system_prompt:
            data={'conflicts':[]}
        elif 'map evidence' in system_prompt:
            data={'facts_used':[{'claim':f'Cedar has {count} beds.','source_span':f'Cedar has {count} beds.','source_id':str(source.id)}
                              for source,count in zip(sources,[12,18])]}
        elif 'JSON OUTPUT SCHEMA' in system_prompt:
            data={'content':'\n\n'.join('## '+title+'\nCedar has 12 beds. Cedar has 18 beds. Conflict: the sources disagree.'
                for title in get_blueprint('executive_summary').sections),
                'facts_used':[{'claim':f'Cedar has {count} beds.','source_span':f'Cedar has {count} beds.','source_id':str(source.id)}
                              for source,count in zip(sources,[12,18])]}
        else:
            data={'passed':True,'reasoning':'Local mock review.','issues':[],'failing_claims':[],'violations':[]}
        return json.dumps(data),{'input_tokens':10,'output_tokens':10}
    monkeypatch.setattr('agents.llm._call_llm_impl',invoke)


async def analyzed(client,db,session_factory,monkeypatch):
    sources=await seed(db);provider(monkeypatch,sources)
    response=await client.post('/api/v1/source-analyses',json={'source_ids':[str(s.id) for s in sources],
        'budget_ceiling':200000,'request_id':str(uuid4())})
    assert response.status_code==202,response.text
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    response=await client.get('/api/v1/source-analyses/'+response.json()['id'])
    assert response.status_code==200,response.text
    data=response.json()
    assert data['status']=='completed',data
    return sources,data


async def test_analysis_deduplicates_and_flags_numeric_conflicts(client,db_session,session_factory,monkeypatch):
    sources,data=await analyzed(client,db_session,session_factory,monkeypatch)
    assert data['unique_facts']==3
    common=next(f for f in data['facts'] if f['claim']=='Cedar opened in 2026.')
    assert {a['source_id'] for a in common['anchors']}=={str(s.id) for s in sources}
    assert len(data['conflicts'])==1 and data['conflicts'][0]['kind']=='numeric'
    assert len(data['conflicts'][0]['facts'])==2
    assert len((await client.get('/api/v1/generations/')).json())==0


async def test_combined_generation_and_each_source_anchor(client,db_session,session_factory,monkeypatch):
    sources,data=await analyzed(client,db_session,session_factory,monkeypatch)
    payload={'source_ids':[str(s.id) for s in sources],'analysis_id':data['id'],
        'conflict_resolutions':{c['id']:{'choice':'preserve'} for c in data['conflicts']},
        'output_types':['executive_summary'],'budget_ceiling':200000}
    response=await client.post('/api/v1/generations/',json=payload)
    assert response.status_code==202,response.text
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    gid=response.json()['id'];result=await client.get('/api/v1/generations/'+gid)
    assert result.status_code==200,result.text
    data=result.json();assert len(data['source_documents'])==2
    assert data['artifacts'],data
    artifact=data['artifacts'][0]
    assert artifact['assurance_status']=='checks_passed',artifact.get('review_results')
    assert {a['source_id'] for c in artifact['evidence']['claims'] for a in c['anchors']}=={str(s.id) for s in sources}
    for claim in artifact['evidence']['claims']:
        for a in claim['anchors']:
            response=await client.get('/api/v1/sources/'+a['source_id']+'/text',params={'generation_id':gid,'expected_version':a['source_version']})
            assert response.status_code==200
            assert response.json()['text'][a['start']:a['end']]==a['text']
    # Secondary sources are protected just like the primary document.
    assert (await client.delete('/api/v1/sources/'+str(sources[1].id))).status_code==409
    exported=await client.get('/api/v1/artifacts/'+artifact['id']+'/export',params={'format':'md','target':'original',
        'expected_hash':artifact['evidence']['content_version'],'citations':True,'provenance':True})
    assert exported.status_code==200
    assert all(str(s.id) in exported.text for s in sources)
    # Saved output reviews must retain every source snapshot and conflict rule.
    saved=await client.post('/api/v1/artifacts/'+artifact['id']+'/versions',json={
        'source':'original','request_id':str(uuid4())})
    assert saved.status_code==201,saved.text
    vid=saved.json()['id']
    task=await client.post(f"/api/v1/artifacts/{artifact['id']}/versions/{vid}/tasks",json={
        'operation':'review','budget_ceiling':200000,'request_id':str(uuid4())})
    assert task.status_code==202,task.text
    assert await run_once(factory=session_factory)
    reviewed=await client.get(f"/api/v1/artifacts/{artifact['id']}/versions/{vid}")
    assert reviewed.status_code==200,reviewed.text
    version_artifact=reviewed.json()['artifact']
    assert version_artifact['assurance_status']=='checks_passed',version_artifact
    assert {a['source_id'] for c in version_artifact['evidence']['claims'] for a in c['anchors']}=={str(s.id) for s in sources}
    # Changing a secondary document invalidates generation/export access instead of using stale evidence.
    await db_session.execute(update(Source).where(Source.id==sources[1].id).values(extracted_text='Changed text.'))
    await db_session.commit()
    assert (await client.get('/api/v1/generations/'+gid)).status_code==409
    assert (await client.get('/api/v1/artifacts/'+artifact['id']+'/export',params={'format':'md','expected_hash':artifact['evidence']['content_version']})).status_code==409


async def test_collections_are_private_versioned_and_reversible(client,db_session,monkeypatch):
    monkeypatch.setenv('API_KEYS','test-key:alice:analyst,other:bob:analyst');monkeypatch.setattr('api.dependencies._API_KEYS',set())
    sources=await seed(db_session)
    body={'name':'Garden sources','source_ids':[str(s.id) for s in sources]}
    first=await client.post('/api/v1/collections',json=body);assert first.status_code==201,first.text
    cid=first.json()['id']
    assert (await client.get('/api/v1/collections/'+cid,headers={'X-API-Key':'other'})).status_code==404
    assert (await client.get('/api/v1/collections',headers={'X-API-Key':'other'})).json()==[]
    changed=await client.put('/api/v1/collections/'+cid,json={**body,'expected_revision':1,'name':'Updated garden'})
    assert changed.status_code==200 and changed.json()['revision']==2
    assert (await client.put('/api/v1/collections/'+cid,json={**body,'expected_revision':1})).status_code==409
    assert (await client.post('/api/v1/collections/'+cid+'/archive')).status_code==200
    assert (await client.get('/api/v1/collections')).json()==[]
    assert (await client.post('/api/v1/collections/'+cid+'/restore')).status_code==200
    assert len((await client.get('/api/v1/collections')).json())==1


async def test_analysis_idempotency_private_access_and_cancellation(client,db_session,monkeypatch):
    monkeypatch.setenv('API_KEYS','test-key:alice:analyst,other:bob:analyst');monkeypatch.setattr('api.dependencies._API_KEYS',set())
    sources=await seed(db_session)
    body={'source_ids':[str(s.id) for s in sources],'budget_ceiling':50000,'request_id':str(uuid4())}
    first=await client.post('/api/v1/source-analyses',json=body)
    assert first.status_code==202
    aid=first.json()['id']
    assert (await client.post('/api/v1/source-analyses',json=body)).json()==first.json()
    assert (await client.post('/api/v1/source-analyses',json={**body,'budget_ceiling':70000})).status_code==409
    assert (await client.get('/api/v1/source-analyses/'+aid,headers={'X-API-Key':'other'})).status_code==404
    assert (await client.get('/api/v1/source-analyses',headers={'X-API-Key':'other'})).json()==[]
    assert (await client.post('/api/v1/source-analyses/'+aid+'/cancel')).status_code==200
    assert (await client.get('/api/v1/source-analyses/'+aid)).json()['status']=='cancelled'


async def test_invalid_analysis_selection_and_resolution_are_rejected(client,db_session,session_factory,monkeypatch):
    sources,data=await analyzed(client,db_session,session_factory,monkeypatch)
    base={'source_ids':[str(s.id) for s in sources],'analysis_id':data['id'],'output_types':['executive_summary']}
    assert (await client.post('/api/v1/generations/',json=base)).status_code==422
    decisions={c['id']:{'choice':'prefer','preferred_source_id':str(uuid4())} for c in data['conflicts']}
    assert (await client.post('/api/v1/generations/',json={**base,'conflict_resolutions':decisions})).status_code==422
    assert (await client.post('/api/v1/generations/',json={'source_ids':base['source_ids'],'output_types':base['output_types']})).status_code==422
    assert (await client.get('/api/v1/sources/'+str(sources[0].id)+'/text',params={'generation_id':data['id'],'expected_version':'0'*64})).status_code==409


async def test_removed_secondary_source_blocks_worker_without_model_calls(client,db_session,session_factory,monkeypatch):
    sources=await seed(db_session);provider(monkeypatch,sources)
    first=await client.post('/api/v1/source-analyses',json={'source_ids':[str(s.id) for s in sources],'budget_ceiling':50000,'request_id':str(uuid4())})
    from orchestrator.runtime import utcnow
    await db_session.execute(update(Source).where(Source.id==sources[1].id).values(deleted_at=utcnow()));await db_session.commit()
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    result=(await client.get('/api/v1/source-analyses/'+first.json()['id'])).json()
    assert result['status']=='unavailable' and result['facts']==[] and result['conflicts']==[]
    assert result['job']['status']=='failed'
    assert await db_session.scalar(select(func.count(LLMCall.id)))==0


async def test_strictest_sensitivity_and_unused_library_counts(client,db_session,monkeypatch):
    sources=await seed(db_session)
    async def no_network(*args,**kwargs):
        return json.dumps({'passed':True,'violations':[],'reasoning':'Local test only.'}),{'input_tokens':0,'output_tokens':0}
    monkeypatch.setattr('agents.llm._call_llm_impl',no_network)
    sources[1].sensitivity=SensitivityLevel.CONFIDENTIAL
    unused=Source(filename='Unused.txt',extracted_text='Unused source text.',sensitivity=SensitivityLevel.PUBLIC,sensitivity_source=SensitivitySource.OPERATOR)
    db_session.add(unused);await db_session.commit()
    first=await client.post('/api/v1/source-analyses',json={'source_ids':[str(s.id) for s in sources],'budget_ceiling':50000,'request_id':str(uuid4())})
    generation=await db_session.get(Generation,UUID(first.json()['id']))
    source=await load_context(db_session,generation)
    assert source.sensitivity==SensitivityLevel.CONFIDENTIAL
    from agents.reviewers import ComplianceReviewer
    from schemas.generation import GenerationParams
    from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION
    context=MINIMAL_EXTRACTION.model_copy(update={'sensitivity':source.sensitivity,'sensitivity_source':'operator'})
    result=await ComplianceReviewer().review('Public-facing text',context,GenerationParams(output_type='linkedin_post'))
    assert result.passed is False
    listed=(await client.get('/api/v1/sources/library',params={'limit':100})).json()['items']
    assert next(s for s in listed if s['id']==str(unused.id))['generation_count']==0
    assert all(next(s for s in listed if s['id']==str(source.id))['generation_count']==1 for source in sources)


def test_conflict_policies_cannot_silently_pick_a_winner():
    from synthesis.extraction import conflicts_check
    conflict={'id':'c','fact_keys':['a','b'],'facts':[{'fact_key':'a','anchors':[{'source_id':'one'}]},
        {'fact_key':'b','anchors':[{'source_id':'two'}]}],'resolution':{'choice':'preserve'}}
    assert not conflicts_check('Only A.',[{'fact_key':'a'}],[conflict])['passed']
    assert conflicts_check('Conflict: A and B.',[{'fact_key':'a'},{'fact_key':'b'}],[conflict])['passed']
    conflict['resolution']={'choice':'omit'}
    assert not conflicts_check('A.',[{'fact_key':'a'}],[conflict])['passed']
    assert conflicts_check('Other facts.',[],[conflict])['passed']
    conflict['resolution']={'choice':'prefer','preferred_source_id':'one'}
    assert not conflicts_check('Conflict: B.',[{'fact_key':'b'}],[conflict])['passed']
    assert conflicts_check('विरोधाभास स्पष्ट है।',[{'fact_key':'a','conflict_notice':'विरोधाभास स्पष्ट है।','conflict_ids':['c']}],[conflict])['passed']


def test_cross_document_calculation_uses_each_local_quote_range():
    docs={}
    operands=[]
    for sid,value in [('a','12'),('b','18')]:
        text=f'Count: {value}.';docs[sid]={'id':sid,'filename':sid,'text':text,'source_version':version(text)}
        operands.append({'source_id':sid,'source_version':version(text),'source_span':text,'start_char':0,'end_char':len(text),'value':value})
    claim='Calculation: Total is 30.'
    result=validate_evidence(claim,[{'claim':claim,'claim_type':'calculation','calculation':{'operation':'sum','inputs':operands,'result':'30'}}],docs,'a')
    assert result['passed'] and result['anchors_matched']==2


def test_same_quote_in_other_document_cannot_substitute_an_anchor():
    documents={'a':{'id':'a','text':'Twelve beds.','source_version':version('Twelve beds.'),'filename':'A'},
               'b':{'id':'b','text':'Other text.','source_version':version('Other text.'),'filename':'B'}}
    citation={'claim':'Twelve beds.','source_span':'Twelve beds.','start_char':0,'end_char':12,'source_id':'b'}
    report=validate_evidence('Twelve beds.',[citation],documents,'a')
    assert not report['passed'] and report['anchors_matched']==0
    citation['source_id']='a'
    assert validate_evidence('Twelve beds.',[citation],documents,'a')['passed']
