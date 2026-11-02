"""Version acceptance tests: lost responses, conflicts, isolation and exact-version review."""
import json
import asyncio
import re
from io import BytesIO
from uuid import uuid4, UUID
from zipfile import ZipFile
import pytest
from sqlalchemy import select, func
from db.models import Source, Generation, Artifact, ArtifactVersion, VersionReview, LLMCall
from schemas.enums import SensitivityLevel, SensitivitySource, GenerationStatus, ArtifactReviewStatus
from revisions.content import digest, sections, replace_section


async def seed(db):
    source = Source(filename='Fixture.txt', extracted_text='Acme Corp launched Widget X.',
        sensitivity=SensitivityLevel.PUBLIC, sensitivity_source=SensitivitySource.OPERATOR)
    db.add(source); await db.flush()
    gen = Generation(source_id=source.id, output_types=['executive_summary'], params={}, status=GenerationStatus.COMPLETED)
    db.add(gen); await db.flush()
    content = '# Overview\nAcme Corp launched Widget X.\n\n# Next steps\nRecommendation: assess adoption.\n'
    artifact = Artifact(generation_id=gen.id, output_type='executive_summary', content=content,
                        review_results=[], facts_used=[], review_status=ArtifactReviewStatus.PASSED)
    db.add(artifact); await db.commit()
    return artifact, source


async def save(client, artifact, content='Edited 🧪 हिंदी 中文', revision=0, request_id=None):
    return await client.put(f'/api/v1/artifacts/{artifact.id}/draft', json={
        'content': content, 'expected_revision': revision, 'base_hash': digest(artifact.content),
        'request_id': request_id or str(uuid4())})


async def snapshot(client, artifact, **kwargs):
    response = await client.post(f'/api/v1/artifacts/{artifact.id}/versions', json={
        'source': 'original', 'request_id': str(uuid4()), **kwargs})
    assert response.status_code == 201, response.text
    return response.json()


async def test_draft_idempotency_conflict_and_original_preservation(client, db_session):
    artifact, _ = await seed(db_session)
    base = f'/api/v1/artifacts/{artifact.id}'
    assert (await client.get(base + '/workspace')).json()['draft']['revision'] == 0
    rid = str(uuid4())
    first = await save(client, artifact, request_id=rid)
    assert first.status_code == 200 and first.json()['revision'] == 1
    assert (await save(client, artifact, request_id=rid)).json() == first.json()
    assert (await save(client, artifact, 'different', request_id=rid)).status_code == 409
    conflict = await save(client, artifact, 'other tab', revision=0)
    assert conflict.status_code == 409 and conflict.json()['detail']['draft']['content'] == first.json()['content']
    await db_session.refresh(artifact)
    assert artifact.content.startswith('# Overview') and artifact.review_status == ArtifactReviewStatus.PASSED


async def test_versions_restore_backup_and_retry(client, db_session):
    artifact, _ = await seed(db_session)
    base = f'/api/v1/artifacts/{artifact.id}'
    original = await snapshot(client, artifact)
    assert original['artifact']['assurance_status'] == 'unreviewed'
    assert (await save(client, artifact, 'Working copy')).status_code == 200
    request = {'expected_revision': 1, 'request_id': str(uuid4())}
    restored = await client.post(base + f"/versions/{original['id']}/restore", json=request)
    assert restored.status_code == 200 and restored.json()['revision'] == 2
    assert (await client.post(base + f"/versions/{original['id']}/restore", json=request)).json() == restored.json()
    versions = (await client.get(base + '/versions')).json()
    assert versions['total'] == 2
    backup = (await client.get(base + f"/versions/{versions['items'][0]['id']}")).json()
    assert backup['content'] == 'Working copy'
    diff = (await client.get(base + '/compare', params={'left': original['id'], 'right': backup['id']})).json()
    assert '+Working copy' in diff['diff']


async def test_private_versions_drafts_exports(client, db_session, monkeypatch):
    monkeypatch.setenv('API_KEYS', 'test-key:alice:analyst,other-key:bob:analyst')
    monkeypatch.setattr('api.dependencies._API_KEYS', set())
    artifact, _ = await seed(db_session)
    await save(client, artifact)
    version = await snapshot(client, artifact)
    base = f'/api/v1/artifacts/{artifact.id}'
    headers = {'X-API-Key': 'other-key'}
    assert (await client.get(base + '/workspace', headers=headers)).json()['draft']['revision'] == 0
    assert (await client.get(base + '/versions', headers=headers)).json()['total'] == 0
    assert (await client.get(base + f"/versions/{version['id']}", headers=headers)).status_code == 404
    assert (await client.get(base + '/export', params={'format':'md', 'target':'version',
        'version_id':version['id'], 'expected_hash':version['content_hash']}, headers=headers)).status_code == 404


async def test_import_keeps_draft_and_stale_export_rejected(client, db_session):
    artifact, _ = await seed(db_session)
    await save(client, artifact, 'Server draft')
    version = await snapshot(client, artifact, source='import', content='Legacy device draft', label='Imported')
    base = f'/api/v1/artifacts/{artifact.id}'
    assert (await client.get(base + '/workspace')).json()['draft']['content'] == 'Server draft'
    assert version['content'] == 'Legacy device draft'
    assert (await client.get(base + '/export', params={'format':'txt', 'target':'draft',
        'expected_revision':0, 'expected_hash':digest('Server draft')})).status_code == 409


@pytest.mark.parametrize('format', ['md','txt','docx','pptx'])
async def test_export_preserves_unicode_tables_long_text(client, db_session, format):
    artifact, _ = await seed(db_session)
    if format == 'pptx':
        artifact.output_type = 'presentation'; await db_session.commit()
    content = '# Findings\nUnicode हिंदी 中文 🧪\n\n| Name | Value |\n|---|---|\n| Test | 42 |\n\n' + 'Long paragraph endmarker ' * 250
    version = await snapshot(client, artifact, source='import', content=content)
    response = await client.get(f'/api/v1/artifacts/{artifact.id}/export', params={
        'target':'version', 'version_id':version['id'], 'expected_hash':version['content_hash'],
        'format':format, 'provenance':True})
    assert response.status_code == 200, response.text[:200] if format in ['md','txt'] else response.status_code
    assert response.headers['cache-control'] == 'no-store'
    if format in ['md','txt']:
        assert 'हिंदी 中文 🧪' in response.text and response.text.count('endmarker') == 250
    else:
        with ZipFile(BytesIO(response.content)) as archive:
            names = [n for n in archive.namelist() if n == 'word/document.xml' or n.startswith('ppt/slides/slide') and n.endswith('.xml')]
            text = ''.join(archive.read(name).decode() for name in names)
            assert 'हिंदी' in text and '中文' in text and '🧪' in text
            assert text.count('endmarker') == 250
            assert '<a:tbl>' in text if format == 'pptx' else '<w:tbl>' in text


def test_section_ids_and_boundaries():
    original = '# Top\nPrefix 🧪\n## Section\nold\n### Child\nchild\n## Sibling\nunchanged\n'
    section = sections(original)[1]
    replaced = replace_section(original, section['id'], 'new\n### Child\nupdated')
    assert replaced.startswith(original[:section['body_start']])
    assert replaced.endswith(original[section['end']:])
    with pytest.raises(ValueError): replace_section(original, section['id'], '## Sibling\ninvalid')
    with pytest.raises(ValueError): replace_section(original + 'changed', section['id'], 'new')


def test_plain_export_removes_complete_emphasis_delimiters():
    from revisions.exports import plain
    assert plain('**Bold** *italic* __also bold__ `code`') == 'Bold italic also bold code'


async def test_pdf_export_uses_real_converter(client, db_session):
    import shutil
    if not (shutil.which('libreoffice') or shutil.which('soffice')):
        pytest.skip('Real LibreOffice conversion is verified in the Docker suite.')
    artifact, _ = await seed(db_session)
    version = await snapshot(client, artifact, source='import', content='# Export\nUnicode हिंदी 中文\n\n' + 'Preserved text. ' * 500 + 'END_MARKER')
    response = await client.get(f'/api/v1/artifacts/{artifact.id}/export', params={'format':'pdf', 'target':'version',
        'version_id':version['id'], 'expected_hash':version['content_hash']})
    assert response.status_code == 200 and response.content.startswith(b'%PDF')
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(response.content)
    text = ''.join(page.get_textpage().get_text_range() for page in document)
    text = re.sub(r'\s+', ' ', text)
    # PDF extraction may interleave the next page's footer between two body words.
    assert len(document) > 1 and len(re.findall(r'\bPreserved\b', text)) == 500
    assert len(re.findall(r'\btext\.', text)) == 500 and 'END_MARKER' in text


async def test_export_filename_is_exposed_to_browser(client, db_session):
    artifact, _ = await seed(db_session)
    response = await client.get(f'/api/v1/artifacts/{artifact.id}/export', params={
        'format':'txt', 'target':'original', 'expected_hash':digest(artifact.content)},
        headers={'Origin':'http://localhost:3000'})
    assert response.status_code == 200
    assert 'content-disposition' in response.headers['access-control-expose-headers'].lower()
    assert 'executive_summary-original-' in response.headers['content-disposition']


async def test_durable_review_exact_text_and_regeneration(client, db_session, session_factory, monkeypatch):
    artifact, source = await seed(db_session)
    from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION
    seen = []
    async def invoke(client, model, system_prompt, user_content, *args, **kwargs):
        seen.append((system_prompt, user_content))
        if 'Knowledge Extraction analyst' in system_prompt:
            data = MINIMAL_EXTRACTION.model_dump(mode='json')
            data['facts'][0]['end_char'] = len('Acme Corp launched Widget X')
        elif 'map evidence' in system_prompt:
            data = {'facts_used':[{'claim':'Acme Corp launched Widget X.', 'source_span':'Acme Corp launched Widget X', 'start_char':0, 'end_char':len('Acme Corp launched Widget X')}]}
        elif 'revise one Markdown section' in system_prompt:
            data = {'content':'Recommendation: assess demand before committing.'}
        else:
            data = {'passed':True, 'issues':[], 'violations':[], 'failing_claims':[], 'reasoning':'Fixture review'}
        return json.dumps(data), {'input_tokens':10, 'output_tokens':10}
    monkeypatch.setattr('agents.llm._call_llm_impl', invoke)
    edited = '# Overview\nAcme Corp launched Widget X.\n\n# Next steps\nRecommendation: assess demand.\n'
    version = await snapshot(client, artifact, source='import', content=edited)
    base = f'/api/v1/artifacts/{artifact.id}'
    task_request = {'operation':'review', 'budget_ceiling':200000, 'request_id':str(uuid4())}
    submitted = await client.post(base + f"/versions/{version['id']}/tasks", json=task_request)
    assert submitted.status_code == 202, submitted.text
    assert (await client.post(base + f"/versions/{version['id']}/tasks", json=task_request)).json() == submitted.json()
    from orchestrator.queue import run_once
    assert await run_once(factory=session_factory)
    async with session_factory() as db:
        from db.models import DurableJob
        job = await db.get(DurableJob, UUID(submitted.json()['job_id']))
        assert job.status == 'completed', job.message
        reviews = (await db.execute(select(VersionReview))).scalars().all()
        assert len(reviews) == 1
        assert reviews[0].content_hash == digest(edited)
        assert len(reviews[0].results) == 5
        assert await db.scalar(select(func.count(LLMCall.id))) == 5
    assert any(edited in user for system, user in seen if 'Fact Reviewer' in system)
    refreshed = (await client.get(base + f"/versions/{version['id']}")).json()
    # Required format headings are missing; a mocked semantic pass cannot certify the version.
    assert refreshed['artifact']['assurance_status'] == 'needs_review'
    task_request = {'operation':'section', 'section_id':version['sections'][1]['id'], 'budget_ceiling':200000, 'request_id':str(uuid4())}
    response = await client.post(base + f"/versions/{version['id']}/tasks", json=task_request)
    assert response.status_code == 202
    assert await run_once(factory=session_factory)
    tasks = (await client.get(base + '/version-tasks')).json()
    assert tasks[0]['job']['status'] == 'completed', tasks
    result = (await client.get(base + f"/versions/{tasks[0]['result_version_id']}")).json()
    assert result['content'].startswith('# Overview\nAcme Corp launched Widget X.')
    assert result['artifact']['assurance_status'] == 'unreviewed'
    history = (await client.get('/api/v1/generations/')).json()
    assert all(g['id'] not in [t['job_id'] for t in tasks] for g in history)


async def test_parallel_draft_saves_have_one_winner(db_session, session_factory):
    from api.routes.workspaces import save_draft
    from schemas.workspace import DraftSave
    from fastapi import HTTPException
    artifact, _ = await seed(db_session)
    async def attempt(content):
        async with session_factory() as db:
            try:
                return await save_draft(artifact.id, DraftSave(content=content, expected_revision=0,
                    base_hash=digest(artifact.content), request_id=uuid4()), db, 'same-owner')
            except HTTPException as exc:
                await db.rollback()
                return exc.status_code
    results = await asyncio.gather(attempt('First tab'), attempt('Second tab'))
    assert sum(isinstance(item, dict) and item['revision'] == 1 for item in results) == 1
    assert results.count(409) == 1


async def test_tiny_budget_fails_without_provider_calls(client, db_session, session_factory, monkeypatch):
    artifact, _ = await seed(db_session)
    version = await snapshot(client, artifact)
    async def forbidden(*args, **kwargs): raise AssertionError('Provider must not be called outside the budget')
    monkeypatch.setattr('agents.llm._call_llm_impl', forbidden)
    result = await client.post(f'/api/v1/artifacts/{artifact.id}/versions/{version["id"]}/tasks', json={
        'operation':'review', 'budget_ceiling':1, 'request_id':str(uuid4())})
    assert result.status_code == 202
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    async with session_factory() as db:
        from db.models import DurableJob
        job = await db.get(DurableJob, UUID(result.json()['job_id']))
        assert job.status == 'failed'
        assert await db.scalar(select(func.count(LLMCall.id))) == 0
        assert await db.scalar(select(func.count(VersionReview.id))) == 0


async def test_full_regeneration_creates_unreviewed_copy(client, db_session, session_factory, monkeypatch):
    artifact, _ = await seed(db_session)
    version = await snapshot(client, artifact)
    from tests.fixtures.knowledge_extraction import MINIMAL_EXTRACTION
    async def invoke(client, model, system_prompt, user_content, *args, **kwargs):
        if 'Knowledge Extraction analyst' in system_prompt:
            payload = MINIMAL_EXTRACTION.model_dump(mode='json')
        else:
            payload = {'content':'# New output\nAcme Corp launched Widget X.', 'facts_used':[]}
        return json.dumps(payload), {'input_tokens':10,'output_tokens':10}
    monkeypatch.setattr('agents.llm._call_llm_impl', invoke)
    result = await client.post(f'/api/v1/artifacts/{artifact.id}/versions/{version["id"]}/tasks', json={
        'operation':'full', 'notes':'Shorter', 'budget_ceiling':200000, 'request_id':str(uuid4())})
    assert result.status_code == 202
    from orchestrator.queue import run_once
    await run_once(factory=session_factory)
    tasks = (await client.get(f'/api/v1/artifacts/{artifact.id}/version-tasks')).json()
    assert tasks[0]['job']['status'] == 'completed', tasks
    assert tasks[0]['result_version_id'] != version['id']
    copy = (await client.get(f'/api/v1/artifacts/{artifact.id}/versions/{tasks[0]["result_version_id"]}')).json()
    assert copy['parent_id'] == version['id'] and copy['artifact']['assurance_status'] == 'unreviewed'
    await db_session.refresh(artifact)
    assert artifact.content == version['content']


async def test_version_jobs_cannot_be_cancelled_by_another_operator(client, db_session, monkeypatch):
    monkeypatch.setenv('API_KEYS', 'test-key:alice:analyst,other-key:bob:analyst')
    monkeypatch.setattr('api.dependencies._API_KEYS', set())
    artifact, _ = await seed(db_session)
    version = await snapshot(client, artifact)
    result = await client.post(f'/api/v1/artifacts/{artifact.id}/versions/{version["id"]}/tasks', json={
        'operation':'review', 'budget_ceiling':50000, 'request_id':str(uuid4())})
    job_id = result.json()['job_id']
    headers = {'X-API-Key':'other-key'}
    for path in [f'/api/v1/generations/{job_id}', f'/api/v1/generations/{job_id}/status']:
        assert (await client.get(path, headers=headers)).status_code == 404
    assert (await client.post(f'/api/v1/generations/{job_id}/cancel', headers=headers)).status_code == 404
    assert (await client.post(f'/api/v1/artifacts/{artifact.id}/version-tasks/{job_id}/cancel', headers=headers)).status_code == 404
