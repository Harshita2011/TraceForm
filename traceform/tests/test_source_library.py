"""Phase 3: actual source/preset APIs and all advertised format contracts, without billed calls."""
import io,json
from uuid import UUID
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from db.models import Source,Generation,DurableJob,CreationPreset
from schemas.enums import SensitivityLevel,SensitivitySource
from schemas.formats import FORMAT_LABELS,format_catalog,validate_format
from schemas.generation import GenerationParams
from ingestion.extractors import validate_extraction_length,ExtractionError

async def upload(client,name='Garden.md',text='A garden has 12 beds. Volunteers meet on Saturdays.'):
    response=await client.post('/api/v1/sources/',files={'file':(name,text,'text/plain')},data={'sensitivity':'public'})
    assert response.status_code==201,response.text
    return response.json()

async def test_library_search_pagination_preview_and_restore(client):
    for i in range(14): await upload(client,f'Notes {i:02}.md')
    first=(await client.get('/api/v1/sources/library?limit=12')).json()
    second=(await client.get('/api/v1/sources/library?limit=12&offset=12')).json()
    assert first['total']==14 and len(first['items'])==12 and len(second['items'])==2
    assert not {s['id'] for s in first['items']} & {s['id'] for s in second['items']}
    found=(await client.get('/api/v1/sources/library?q=Notes%2003')).json()['items']
    assert len(found)==1 and found[0]['filename']=='Notes 03.md'
    sid=found[0]['id']; detail=(await client.get(f'/api/v1/sources/{sid}')).json()
    assert '12 beds' in detail['text'] and detail['extraction_method']=='md'
    assert (await client.delete(f'/api/v1/sources/{sid}')).status_code==200
    assert (await client.get('/api/v1/sources/library')).json()['total']==13
    assert (await client.get('/api/v1/sources/library?trash=true')).json()['total']==1
    blocked=await client.post('/api/v1/generations/',json={'source_id':sid,'output_types':['executive_summary']})
    assert blocked.status_code==422
    assert (await client.post(f'/api/v1/sources/{sid}/restore')).status_code==200
    assert (await client.get('/api/v1/sources/library')).json()['total']==14

async def test_linked_source_cannot_be_removed_and_text_remains_available(client):
    source=await upload(client)
    run=await client.post('/api/v1/generations/',json={'source_id':source['id'],'output_types':['executive_summary']})
    assert run.status_code==202
    assert (await client.delete('/api/v1/sources/'+source['id'])).status_code==409
    detail=(await client.get('/api/v1/sources/'+source['id'])).json()
    assert detail['generation_count']==1 and not detail['can_delete']
    assert (await client.get('/api/v1/sources/'+source['id']+'/text')).status_code==200

@pytest.mark.parametrize('name,content', [('empty.txt',''),('spaces.txt','  \n\t'),('binary.txt',b'\x00\x01not text'),('bad.pdf',b'not a pdf'),('bad.docx',b'not a zip'),('program.exe',b'hello')])
async def test_invalid_upload_is_actionable_and_never_saved(client,db_session,name,content):
    response=await client.post('/api/v1/sources/',files={'file':(name,content)},data={'sensitivity':'public'})
    assert response.status_code==422 and response.json()['detail']
    assert (await db_session.execute(select(Source))).scalars().all()==[]

async def test_size_cap_reads_only_bounded_content(client,monkeypatch):
    monkeypatch.setattr('api.routes.sources.MAX_FILE_SIZE_BYTES',32)
    response=await client.post('/api/v1/sources/',files={'file':('large.txt','x'*33)})
    assert response.status_code==422 and '50 MB' in response.text

async def test_explicit_truncation_is_recorded_and_never_implicit(client):
    content='word '*16000
    response=await client.post('/api/v1/sources/',files={'file':('long.txt',content)},data={'sensitivity':'public'})
    assert response.status_code==422
    response=await client.post('/api/v1/sources/',files={'file':('long.txt',content)},data={'sensitivity':'public','truncate_long_content':'true'})
    assert response.status_code==201 and response.json()['was_truncated']
    assert response.json()['word_count']<=15000

async def test_docx_tables_are_extracted(client):
    from docx import Document
    doc=Document();doc.add_paragraph('Garden inventory');table=doc.add_table(rows=1,cols=2)
    table.cell(0,0).text='Beds';table.cell(0,1).text='12';out=io.BytesIO();doc.save(out)
    source=await upload(client,'Inventory.docx',out.getvalue())
    detail=(await client.get('/api/v1/sources/'+source['id'])).json()
    assert 'Beds | 12' in detail['text'] and detail['extraction_method']=='docx'

async def test_pdf_empty_and_encrypted_are_rejected(client):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pdfencrypt import StandardEncryption
    for encrypted in [False,True]:
        stream=io.BytesIO();canvas=Canvas(stream,encrypt=StandardEncryption('private-password') if encrypted else None)
        if encrypted: canvas.drawString(10,50,'Locked document text')
        canvas.showPage();canvas.save()
        response=await client.post('/api/v1/sources/',files={'file':('scan.pdf',stream.getvalue())})
        assert response.status_code==422 and ('PDF' in response.text or 'text' in response.text)

async def test_ocr_low_confidence_and_missing_engine_are_actionable(client,monkeypatch):
    import pytesseract
    from PIL import Image
    stream=io.BytesIO();Image.new('RGB',(20,20),'white').save(stream,format='PNG')
    monkeypatch.setattr(pytesseract,'image_to_data',lambda *a,**k:{'conf':['-1','22.5','30']})
    response=await client.post('/api/v1/sources/',files={'file':('scan.png',stream.getvalue())})
    assert response.status_code==422 and 'confidence' in response.text
    def missing(*a,**k): raise RuntimeError('Tesseract is not installed')
    monkeypatch.setattr(pytesseract,'image_to_data',missing)
    response=await client.post('/api/v1/sources/',files={'file':('scan.png',stream.getvalue())})
    assert response.status_code==422 and 'Tesseract' in response.text

async def test_video_reference_is_not_a_ready_generation_source(client):
    source=await upload(client,'recording.mp4',b'video-reference-fixture')
    assert source['status']=='reference_only' and source['extracted_text_length']==0
    result=await client.post('/api/v1/generations/',json={'source_id':source['id'],'output_types':['executive_summary']})
    assert result.status_code==422

@pytest.mark.parametrize('output_type',list(FORMAT_LABELS))
async def test_new_and_saved_source_admission_for_every_format(client,db_session,output_type):
    source=await upload(client)
    saved=(await client.get('/api/v1/sources/'+source['id'])).json()
    for index,sid in enumerate([source['id'],saved['id']]):
        response=await client.post('/api/v1/generations/',json={'source_id':sid,'output_types':[output_type],
            'params':{'brand_name':'Garden Club','sections':['Next planting day'],'language':'es','detail_level':'low'}})
        assert response.status_code==202,response.text
        run=await db_session.get(Generation,UUID(response.json()['id']))
        assert run.params['sections']==['Next planting day'] and run.params['brand_name']=='Garden Club'
        assert await db_session.get(DurableJob,run.id)

@pytest.mark.parametrize('output_type',list(FORMAT_LABELS))
async def test_every_generator_emits_its_required_structure_with_valid_provider_response(output_type):
    from agents.generators.base import GenericGeneratorAgent
    from agents.generators.blueprints import get_blueprint
    from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION
    content='\n\n'.join('## '+section+'\nAcme Corp launched Widget X. See the cited source for details.' for section in get_blueprint(output_type).sections+['Next steps'])
    response=SimpleNamespace(content=[SimpleNamespace(text=json.dumps({'content':content,'facts_used':[]}))],usage=SimpleNamespace(input_tokens=100,output_tokens=200))
    client=SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)))
    result=await GenericGeneratorAgent(output_type,client=client,model='test-model').generate(MINIMAL_EXTRACTION,GenerationParams(sections=['Next steps'],brand_name='Acme'))
    assert validate_format(output_type,result.content,['Next steps'])['passed']
    prompt=client.messages.create.call_args.kwargs['system']
    assert 'Acme' in prompt and '## Next steps' in prompt

@pytest.mark.parametrize('output_type',list(FORMAT_LABELS))
def test_format_names_in_prose_empty_sections_and_placeholders_do_not_pass(output_type):
    from agents.generators.blueprints import get_blueprint
    sections=get_blueprint(output_type).sections
    assert not validate_format(output_type,' '.join(sections))['passed']
    assert not validate_format(output_type,'\n'.join('## '+s for s in sections))['passed']
    placeholder='\n\n'.join('## '+s+'\nThe source does not provide enough information to complete this section.' for s in sections)
    assert not validate_format(output_type,placeholder)['passed']

async def test_format_catalog_is_exactly_the_advertised_set(client):
    response=await client.get('/api/v1/generations/formats')
    assert response.status_code==200
    assert {c['id'] for c in response.json()}==set(FORMAT_LABELS)
    assert all(c['sections'] and c['version'] and c['deliverable'].startswith('Written') for c in response.json())

async def test_presets_round_trip_update_conflict_delete_and_private_ownership(client,monkeypatch):
    from api import dependencies
    monkeypatch.setattr(dependencies,'_API_KEYS',{'alice-key:alice:admin','bob-key:bob:analyst'})
    monkeypatch.setenv('API_KEYS','alice-key:alice:admin,bob-key:bob:analyst')
    alice={'X-API-Key':'alice-key'};bob={'X-API-Key':'bob-key'}
    body={'name':'Leadership updates','settings':{'output_types':['executive_summary','presentation'],
        'params':{'audience':'executives','tone':'formal','language':'hi','detail_level':'high',
                  'objective':'Prepare a decision','style':'Use plain language','sections':['Open questions'],'brand_name':'Garden Club'}}}
    response=await client.post('/api/v1/presets/',json=body,headers=alice)
    assert response.status_code==201;record=response.json();pid=record['id']
    saved=(await client.get('/api/v1/presets/',headers=alice)).json()[0]
    assert saved['settings']['params']['sections']==['Open questions'] and saved['settings']['params']['brand_name']=='Garden Club'
    assert (await client.get('/api/v1/presets/',headers=bob)).json()==[]
    assert (await client.put('/api/v1/presets/'+pid,json={**body,'expected_revision':1},headers=bob)).status_code==404
    assert (await client.put('/api/v1/presets/'+pid,json={**body,'name':'Updated','expected_revision':1},headers=alice)).json()['revision']==2
    assert (await client.put('/api/v1/presets/'+pid,json={**body,'expected_revision':1},headers=alice)).status_code==409
    assert (await client.delete('/api/v1/presets/'+pid,headers=bob)).status_code==404
    assert (await client.delete('/api/v1/presets/'+pid,headers=alice)).status_code==200
    assert (await client.get('/api/v1/presets/',headers=alice)).json()==[]

@pytest.mark.parametrize('params',[{'sections':['']},{'sections':['line\nbreak']},{'overrides':{'executive_summary':{'sections':'bad'}}}])
async def test_invalid_preset_sections_are_rejected(client,params):
    response=await client.post('/api/v1/presets/',json={'name':'Invalid','settings':{'output_types':['executive_summary'],'params':params}})
    assert response.status_code==422

async def test_incomplete_format_cannot_publish_as_passed_even_when_model_reviewers_pass(session_factory,monkeypatch):
    from db.models import KnowledgeExtractionModel,Artifact
    from schemas.enums import GenerationStatus,ArtifactReviewStatus
    from agents.base import GeneratorArtifactResult
    from schemas.review import ReviewResult
    from orchestrator.jobs import _async_run_generator_task
    from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION
    async with session_factory() as db:
        source=Source(extracted_text='Acme Corp launched Widget X.',sensitivity=SensitivityLevel.PUBLIC,sensitivity_source=SensitivitySource.OPERATOR)
        db.add(source);await db.flush()
        run=Generation(source_id=source.id,output_types=['executive_summary'],params={},status=GenerationStatus.RUNNING)
        extraction=MINIMAL_EXTRACTION
        ke=KnowledgeExtractionModel(source_id=source.id,summary=extraction.summary,entities=extraction.entities.model_dump(),facts=[f.model_dump() for f in extraction.facts],relationships=[],domain=extraction.domain,source_tone=extraction.source_tone)
        db.add_all([run,ke]);await db.commit()
    class Generator:
        async def generate(self,*a,**k):
            return GeneratorArtifactResult('executive_summary','Acme Corp launched Widget X.',[],'test','test',{})
    class Reviewer:
        version='test'
        async def review(self,*a,**k):
            return ReviewResult(reviewer_name='test',passed=True,details={},reviewer_version='test')
    monkeypatch.setattr('orchestrator.jobs.AsyncSessionLocal',session_factory)
    monkeypatch.setattr('orchestrator.jobs.GenericGeneratorAgent',lambda *a,**k:Generator())
    for name in ['StyleReviewer','FactReviewer','ComplianceReviewer']:
        monkeypatch.setattr('orchestrator.jobs.'+name,lambda *a,**k:Reviewer())
    await _async_run_generator_task(None,str(run.id),str(ke.id),'executive_summary','test',0)
    async with session_factory() as db:
        artifact=(await db.execute(select(Artifact))).scalar_one()
        assert artifact.review_status==ArtifactReviewStatus.FAILED
        check=next(r for r in artifact.review_results if r.get('reviewer_name')=='format_reviewer')
        assert not check['passed'] and check['details']['issues']

async def test_failed_start_reuses_source_without_reupload(client,db_session,monkeypatch):
    source=await upload(client)
    payload={'source_id':source['id'],'output_types':['executive_summary']}
    async def unavailable(configuration=None):return {'available':False,'message':'Provider temporarily unavailable'}
    monkeypatch.setattr('agents.availability.provider_health',unavailable)
    assert (await client.post('/api/v1/generations/',json=payload,headers={'Idempotency-Key':'preserved-start'})).status_code==503
    async def ready(configuration=None):return {'available':True,'message':'Ready'}
    monkeypatch.setattr('agents.availability.provider_health',ready)
    assert (await client.post('/api/v1/generations/',json=payload,headers={'Idempotency-Key':'preserved-start'})).status_code==202
    assert len((await db_session.execute(select(Source))).scalars().all())==1
    assert len((await db_session.execute(select(Generation))).scalars().all())==1

def test_truncation_uses_any_whitespace_without_losing_complete_lines():
    text='Start here\n'+'word\n'*16000
    kept,truncated=validate_extraction_length(text,operator_truncate=True)
    assert truncated and len(kept.split())==15000

async def test_configured_ocr_returns_ready_source_and_records_method(client,monkeypatch):
    import pytesseract
    from PIL import Image
    stream=io.BytesIO();Image.new('RGB',(20,20),'white').save(stream,format='PNG')
    monkeypatch.setattr(pytesseract,'image_to_data',lambda *a,**k:{'conf':['-1','90.5','95']})
    monkeypatch.setattr(pytesseract,'image_to_string',lambda *a,**k:'Garden has 12 raised beds.')
    source=await upload(client,'scan.png',stream.getvalue())
    assert source['status']=='ready' and source['extraction_method']=='ocr'
