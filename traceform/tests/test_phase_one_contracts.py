"""Phase 1: live data must not be replaced with illustrative successes."""
from db.models import EvaluationRun, Artifact
from schemas.enums import ArtifactReviewStatus
from tests.test_workspace_workflow import make_run


async def test_no_evaluation_returns_null(client):
    response = await client.get('/api/v1/evaluations/latest')
    assert response.status_code == 200
    assert response.json() is None


async def test_evaluation_preserves_zero_and_does_not_infer_other_metrics(client, db_session):
    db_session.add(EvaluationRun(dataset_version='test-v1', dataset_size=4,
                                 fact_accuracy=0.0, style_adherence_rate=None))
    await db_session.commit()
    latest = (await client.get('/api/v1/evaluations/latest')).json()
    assert latest['fact_accuracy'] == 0.0
    assert latest['style_adherence_rate'] is None
    assert latest['citation_coverage'] is None
    assert latest['hallucination_rate'] is None
    assert latest['dataset_size'] == 4
    history = (await client.get('/api/v1/evaluations/history')).json()
    assert history[0]['citation_coverage'] is None


async def test_evaluations_require_authentication(client):
    for path in ('latest', 'history'):
        response = await client.get(f'/api/v1/evaluations/{path}', headers={'X-API-Key': ''})
        assert response.status_code == 401


async def test_artifact_id_routes_match_workspace_contract(client, db_session):
    run = await make_run(db_session)
    artifact = Artifact(generation_id=run.id, output_type='executive_summary', content='A source-backed output.',
                        review_status=ArtifactReviewStatus.PASSED, review_results=[], facts_used=[])
    db_session.add(artifact)
    await db_session.commit()
    response = await client.get(f'/api/v1/artifacts/{artifact.id}')
    assert response.status_code == 200
    assert response.json()['content'] == 'A source-backed output.'
    assert response.json()['review_results'] == []
    feedback = await client.post(f'/api/v1/artifacts/{artifact.id}/feedback', json={'rating':'positive','comment':'Useful summary'})
    assert feedback.status_code == 200
    assert feedback.json()['feedback']['comment'] == 'Useful summary'


async def test_history_returns_source_identity_and_sensitivity(client, db_session):
    run = await make_run(db_session)
    from db.models import Source
    source = await db_session.get(Source, run.source_id)
    source.raw_content_ref = 'storage_data/source_name_01234567.txt'
    await db_session.commit()
    items = (await client.get('/api/v1/generations/history/list')).json()['items']
    assert items[0]['source_filename'] == 'source_name.txt'
    assert items[0]['sensitivity'] == 'internal'


async def test_historical_constant_is_not_exposed_as_a_measurement(client, db_session):
    run = await make_run(db_session)
    artifact = Artifact(generation_id=run.id, output_type='executive_summary',
                        review_results=[{'_traceform_meta': {'differentiation_score':94, 'uniqueness_score':94}}])
    db_session.add(artifact)
    await db_session.commit()
    response = await client.get(f'/api/v1/artifacts/{artifact.id}')
    assert response.json()['differentiation_score'] is None
    assert response.json()['uniqueness_score'] is None


async def test_artifact_override_contract_records_reason_without_reclassifying_source(client, db_session):
    from db.models import Source
    run = await make_run(db_session)
    artifact = Artifact(generation_id=run.id, output_type='executive_summary',
                        review_status=ArtifactReviewStatus.FAILED, content='Draft',
                        review_results=[{'reviewer_name':'compliance_reviewer','passed':False}])
    db_session.add(artifact)
    await db_session.commit()
    response = await client.post(f'/api/v1/artifacts/{artifact.id}/compliance-override',
                                 json={'reason': 'Reviewed for internal use only'})
    assert response.status_code == 200
    assert response.json()['reason'] == 'Reviewed for internal use only'
    assert (await db_session.get(Source, run.source_id)).sensitivity.value == 'internal'


async def test_production_cannot_publish_synthetic_provider_output(monkeypatch):
    import pytest
    from agents.llm import call_llm
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('TRACEFORM_ALLOW_SYNTHETIC_LLM', 'true')
    with pytest.raises(RuntimeError, match='LLM generation unavailable'):
        await call_llm(None, 'unavailable', 'system', 'source')
