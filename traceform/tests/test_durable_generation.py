"""Durable dispatch, billing-safe recovery, settings and migration integration coverage."""
import asyncio
from datetime import timedelta
from uuid import UUID, uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import select, func, update, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from db.models import (Generation, Source, Artifact, DurableJob, LLMCall, ProviderConfiguration,
                       ActiveProvider, Base)
from schemas.enums import GenerationStatus, ArtifactReviewStatus, SensitivityLevel, SensitivitySource
from orchestrator.runtime import (RunContext, current_run, current_stage, utcnow, plan_fingerprint,
                                  tracked_call, BudgetLimitExceeded, LeaseLost, fence, UncertainCall)
from orchestrator.queue import claim_job, recover_expired, run_once, job_summary


async def seed(factory, budget=50000):
    async with factory() as db:
        source = Source(extracted_text='The project serves 42 customers.', sensitivity=SensitivityLevel.PUBLIC,
                        sensitivity_source=SensitivitySource.OPERATOR, sensitivity_confidence=1)
        config = ProviderConfiguration(provider='gemini', model='test-model', encrypted_key=None,
            pricing={'input': 1, 'output': 2, 'version': 'test', 'origin': 'test'}, created_by='test')
        db.add_all([source, config]); await db.flush()
        gen = Generation(source_id=source.id, output_types=['executive_summary'], params={},
                         status=GenerationStatus.QUEUED, budget_type='tokens', budget_ceiling=budget)
        db.add(gen); await db.flush()
        db.add(DurableJob(generation_id=gen.id, configuration_id=config.id, plan_fingerprint=plan_fingerprint()))
        await db.commit()
        return gen.id, config, source


async def context_for(factory, budget=50000):
    gid, config, source = await seed(factory, budget)
    claim = await claim_job('test-worker', factory)
    return RunContext(gid, claim[1], config, factory), source


async def invoke_call(invoke, content='Source'):
    return await tracked_call(invoke, model='test-model', system_prompt='System', user_content=content,
                              max_tokens=100, temperature=.2, json_mode=False)


async def test_atomic_claim_has_one_owner(session_factory):
    gid, _, _ = await seed(session_factory)
    claims = await asyncio.gather(claim_job('one', session_factory), claim_job('two', session_factory))
    assert sum(c is not None for c in claims) == 1
    async with session_factory() as db:
        assert (await db.get(DurableJob, gid)).attempts == 1


async def test_api_idempotency_and_conflicting_payload(client, db_session):
    source = Source(extracted_text='Valid source text.', sensitivity=SensitivityLevel.PUBLIC,
                    sensitivity_source=SensitivitySource.OPERATOR)
    db_session.add(source); await db_session.commit()
    payload = {'source_id': str(source.id), 'output_types': ['executive_summary']}
    headers = {'Idempotency-Key': 'same-submission'}
    first = await client.post('/api/v1/generations/', json=payload, headers=headers)
    second = await client.post('/api/v1/generations/', json=payload, headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()['id'] == second.json()['id']
    assert await db_session.scalar(select(func.count(DurableJob.generation_id))) == 1
    payload['budget_ceiling'] = 100
    assert (await client.post('/api/v1/generations/', json=payload, headers=headers)).status_code == 409
    job = await db_session.get(DurableJob, UUID(first.json()['id']))
    assert job.status == 'queued' and job.attempts == 0


async def test_saved_call_replays_without_double_usage(session_factory):
    context, _ = await context_for(session_factory)
    count = 0
    async def provider():
        nonlocal count
        count += 1
        return 'Saved response', {'input_tokens': 10, 'output_tokens': 20, 'usage_recorded': True}
    token = current_run.set(context)
    try:
        first = await invoke_call(provider)
        second = await invoke_call(provider)
    finally: current_run.reset(token)
    assert first == second and count == 1
    async with session_factory() as db:
        gen = await db.get(Generation, context.generation_id)
        job = await db.get(DurableJob, gen.id)
        assert gen.total_tokens == gen.budget_used == 30
        assert gen.total_cost_usd == pytest.approx(.00005)
        assert job.reserved_budget == 0
        call = (await db.execute(select(LLMCall))).scalar_one()
        assert call.pricing['version'] == 'test' and call.model == 'test-model'


async def test_parallel_reservations_do_not_oversubscribe(session_factory):
    context, _ = await context_for(session_factory, budget=110)
    calls = 0
    started = asyncio.Event(); release = asyncio.Event()
    async def provider():
        nonlocal calls
        calls += 1; started.set(); await release.wait()
        return 'OK', {'input_tokens': 10, 'output_tokens': 10}
    token = current_run.set(context)
    try:
        first = asyncio.create_task(invoke_call(provider, 'First'))
        await started.wait()
        with pytest.raises(BudgetLimitExceeded): await invoke_call(provider, 'Second')
        release.set(); await first
    finally: current_run.reset(token)
    assert calls == 1


async def test_expired_safe_job_requeues_and_stale_worker_cannot_commit(session_factory):
    context, _ = await context_for(session_factory)
    async with session_factory() as db:
        await db.execute(update(DurableJob).values(lease_until=utcnow()-timedelta(seconds=1)))
        await db.commit()
    await recover_expired(session_factory)
    claim = await claim_job('replacement', session_factory)
    assert claim[1] != context.lease_token
    token = current_run.set(context)
    try:
        async with session_factory() as db:
            with pytest.raises(LeaseLost): await fence(db)
    finally: current_run.reset(token)


async def test_unknown_inflight_request_is_not_repeated(session_factory):
    context, _ = await context_for(session_factory)
    async with session_factory() as db:
        db.add(LLMCall(generation_id=context.generation_id, fingerprint='pending', stage='extract',
            status='started', model='test-model', provider='gemini', pricing={}, reservation=20))
        await db.execute(update(DurableJob).values(lease_until=utcnow()-timedelta(seconds=1)))
        await db.commit()
    await recover_expired(session_factory)
    assert await claim_job('replacement', session_factory) is None
    async with session_factory() as db:
        job = await db.get(DurableJob, context.generation_id)
        assert job.status == 'failed' and 'unknown' in job.message
        assert (await db.execute(select(LLMCall))).scalar_one().status == 'uncertain'


async def test_worker_completion_and_timeout_are_durable(session_factory, monkeypatch):
    gid, _, _ = await seed(session_factory)
    async def finish(_, run_id):
        async with session_factory() as db:
            gen = await db.get(Generation, UUID(run_id)); gen.status = GenerationStatus.COMPLETED
            await db.commit()
    assert await run_once('worker', session_factory, finish)
    async with session_factory() as db:
        job = await db.get(DurableJob, gid)
        assert job.status == 'completed' and job.lease_token is None and job.finished_at
    gid, _, _ = await seed(session_factory)
    monkeypatch.setenv('TRACEFORM_JOB_TIMEOUT_SECONDS', '.02')
    async def hang(*_): await asyncio.sleep(10)
    await run_once('worker', session_factory, hang)
    async with session_factory() as db:
        assert (await db.get(DurableJob, gid)).status == 'failed'
        assert (await db.get(Generation, gid)).status == GenerationStatus.FAILED


async def test_running_cancellation_keeps_saved_output(client, session_factory):
    gid, _, _ = await seed(session_factory)
    started = asyncio.Event()
    async def pipeline(_, run_id):
        async with session_factory() as db:
            db.add(Artifact(generation_id=UUID(run_id), output_type='executive_summary',
                            content='Saved output', review_status=ArtifactReviewStatus.PASSED))
            await fence(db); await db.commit()
        started.set(); await asyncio.sleep(10)
    task = asyncio.create_task(run_once('worker', session_factory, pipeline, lease_seconds=.4))
    await asyncio.wait_for(started.wait(), 5)
    response = await client.post(f'/api/v1/generations/{gid}/cancel')
    assert response.status_code == 200
    await asyncio.wait_for(task, 5)
    async with session_factory() as db:
        assert (await db.get(DurableJob, gid)).status == 'cancelled'
        assert (await db.get(Generation, gid)).status == GenerationStatus.CANCELLED
        assert (await db.execute(select(Artifact))).scalar_one().content == 'Saved output'


async def test_queued_cancel_is_idempotent_and_not_claimed(client, session_factory):
    gid, _, _ = await seed(session_factory)
    assert (await client.post(f'/api/v1/generations/{gid}/cancel')).status_code == 200
    assert (await client.post(f'/api/v1/generations/{gid}/cancel')).status_code == 200
    assert await claim_job('worker', session_factory) is None


async def test_failed_heartbeat_stops_execution_for_safe_recovery(session_factory,monkeypatch):
    from orchestrator import queue
    gid,_,_=await seed(session_factory)
    seen=queue.worker_seen
    calls=0
    async def interrupted(worker_id,factory):
        nonlocal calls
        calls+=1
        if calls>1:raise RuntimeError('Simulated heartbeat storage interruption')
        await seen(worker_id,factory)
    monkeypatch.setattr(queue,'worker_seen',interrupted)
    stopped=asyncio.Event()
    async def pipeline(_,run_id):
        try:await asyncio.sleep(30)
        finally:stopped.set()
    assert await asyncio.wait_for(run_once('heartbeat-worker',session_factory,pipeline,lease_seconds=1),5)
    assert stopped.is_set()
    async with session_factory() as db:
        assert (await db.get(DurableJob,gid)).status=='queued'
        assert (await db.get(Generation,gid)).status==GenerationStatus.QUEUED


async def test_encrypted_settings_permissions_revision_and_job_snapshot(client, db_session, monkeypatch):
    from security.credentials import decrypt_key
    initial = (await client.get('/api/v1/settings/provider')).json()
    payload = {'expected_revision': initial['revision'], 'provider': 'gemini', 'model': 'chosen-model',
               'api_key': 'secret-provider-value', 'input_per_million': .2, 'output_per_million': .5}
    response = await client.put('/api/v1/settings/provider', json=payload)
    assert response.status_code == 200
    assert 'secret-provider-value' not in response.text and 'encrypted_key' not in response.text
    config = (await db_session.execute(select(ProviderConfiguration).where(
        ProviderConfiguration.model == 'chosen-model'))).scalar_one()
    assert config.encrypted_key != payload['api_key'] and decrypt_key(config.encrypted_key) == payload['api_key']
    assert (await client.put('/api/v1/settings/provider', json=payload)).status_code == 409
    from api import dependencies
    monkeypatch.setattr(dependencies, '_API_KEYS', {'restricted:reader:analyst'})
    monkeypatch.setenv('API_KEYS', 'restricted:reader:analyst')
    denied = await client.put('/api/v1/settings/provider', json=payload, headers={'X-API-Key':'restricted'})
    assert denied.status_code == 403
    visible = await client.get('/api/v1/settings/provider', headers={'X-API-Key':'restricted'})
    assert visible.json()['can_edit'] is False


async def test_validation_errors_never_echo_provider_secret(client):
    result = await client.put('/api/v1/settings/provider', json={'api_key': 'private-credential'})
    assert result.status_code == 422 and 'private-credential' not in result.text


async def test_non_destructive_migrations_adopt_existing_schema(tmp_path):
    from db.migrate import migrate
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path}/legacy.db')
    try:
        async with engine.begin() as connection:
            # Represents the previous unversioned schema with existing data.
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("INSERT INTO worker_states(worker_id,last_seen_at) VALUES ('preserve-me',CURRENT_TIMESTAMP)"))
        await migrate(engine); await migrate(engine)
        async with engine.connect() as connection:
            assert (await connection.execute(text('SELECT worker_id FROM worker_states'))).scalar_one() == 'preserve-me'
            assert (await connection.execute(text('SELECT version_num FROM alembic_version'))).scalar_one() == '0009_measured_evaluations'
    finally: await engine.dispose()


async def test_migrations_create_fresh_database(tmp_path):
    from db.migrate import migrate
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path}/fresh.db')
    try:
        await migrate(engine)
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda c: inspect(c).get_table_names())
            assert {'durable_jobs', 'llm_calls', 'generations', 'sources', 'provider_configurations'} <= set(tables)
    finally: await engine.dispose()

async def test_extraction_reuse_requires_matching_source_model_and_contract(session_factory):
    from orchestrator.checkpoints import save_extraction, load_extraction
    from schemas.knowledge import KnowledgeExtraction, Entities, Fact
    context, source = await context_for(session_factory)
    extraction = KnowledgeExtraction(summary='42 customers.', entities=Entities(),
        facts=[Fact(claim='The project serves 42 customers.', source_span=source.extracted_text,
                    start_char=0, end_char=len(source.extracted_text), confidence=1)], relationships=[],
        domain='general', source_tone='formal', sensitivity='public', sensitivity_source='operator', sensitivity_confidence=1)
    token = current_run.set(context)
    try:
        extraction_id = await save_extraction(source, extraction, 'test-model', session_factory)
        reused = await load_extraction(source, 'test-model', session_factory)
        assert reused[1] == extraction_id
        assert await load_extraction(source, 'different-model', session_factory) is None
        source.extracted_text = 'The project serves 99 customers.'
        assert await load_extraction(source, 'test-model', session_factory) is None
    finally: current_run.reset(token)


async def test_resuming_output_updates_checkpoint_and_keeps_passed_output_id(session_factory):
    from orchestrator.jobs import _persist_artifact, _async_generate_output
    context, _ = await context_for(session_factory)
    token = current_run.set(context)
    try:
        async with session_factory() as db:
            old = Artifact(generation_id=context.generation_id, output_type='executive_summary',
                           content='Unfinished', review_status=ArtifactReviewStatus.FAILED, retry_count=0,
                           counted_as_eval_failure=False)
            db.add(old); await db.commit(); output_id = old.id
        async with session_factory() as db:
            replacement = Artifact(generation_id=context.generation_id, output_type='executive_summary',
                content='Complete', review_status=ArtifactReviewStatus.PASSED, retry_count=0,
                counted_as_eval_failure=False)
            saved = await _persist_artifact(db, replacement); await db.commit()
            assert saved.id == output_id
        # The completed output is skipped before reading extraction/provider state.
        await _async_generate_output(None, str(context.generation_id), str(uuid4()), 'executive_summary', 'test-model', 0)
        async with session_factory() as db:
            rows = (await db.execute(select(Artifact))).scalars().all()
            assert len(rows) == 1 and rows[0].content == 'Complete'
    finally: current_run.reset(token)


@pytest.mark.parametrize('message', ['401 bad api key', '429 quota exhausted', '503 provider busy'])
async def test_provider_failures_save_guidance_and_block_same_call_replay(session_factory, message):
    context, _ = await context_for(session_factory)
    attempts = 0
    async def broken():
        nonlocal attempts
        attempts += 1
        raise RuntimeError(message)
    token = current_run.set(context)
    try:
        with pytest.raises(RuntimeError): await invoke_call(broken)
        with pytest.raises(UncertainCall): await invoke_call(broken)
    finally: current_run.reset(token)
    async with session_factory() as db:
        call = (await db.execute(select(LLMCall))).scalar_one()
        assert call.status == 'failed' and call.error and message not in call.error
    assert attempts == 1


async def test_unknown_usage_retains_reservation_instead_of_reporting_free_call(session_factory):
    context, _ = await context_for(session_factory)
    async def provider(): return 'No usage metadata', {'input_tokens':0, 'output_tokens':0, 'usage_recorded':False}
    token = current_run.set(context)
    try: await invoke_call(provider)
    finally: current_run.reset(token)
    async with session_factory() as db:
        summary = await job_summary(db, context.generation_id)
        assert summary['usage_incomplete'] and summary['reserved_budget'] > 0


async def test_job_keeps_immutable_configuration_when_active_settings_change(session_factory):
    gid, config, _ = await seed(session_factory)
    async with session_factory() as db:
        replacement = ProviderConfiguration(provider='anthropic', model='replacement', encrypted_key=None,
            pricing={'input':99, 'output':99, 'version':'changed'}, created_by='test')
        db.add(replacement); await db.flush()
        db.add(ActiveProvider(id=1, configuration_id=replacement.id, revision=2)); await db.commit()
        summary = await job_summary(db, gid)
        assert summary['model'] == config.model and summary['provider'] == config.provider
        assert summary['pricing']['version'] == 'test'

async def test_worker_process_restart_replays_saved_response_without_new_provider_call(session_factory, test_engine, tmp_path):
    """Kill a real worker after a response commit, then resume using a new process."""
    import os
    import sys
    import subprocess
    gid, _, _ = await seed(session_factory)
    script = tmp_path / 'interrupted_worker.py'
    marker, counter = tmp_path / 'checkpoint', tmp_path / 'provider-count'
    script.write_text('''import asyncio,sys
from pathlib import Path
from uuid import UUID
from db.session import AsyncSessionLocal, engine
from db.models import Generation, Artifact
from schemas.enums import GenerationStatus, ArtifactReviewStatus
from orchestrator.queue import run_once
from orchestrator.runtime import tracked_call, fence
async def pipeline(_, run_id):
    async def provider():
        with Path(sys.argv[3]).open('a') as stream: stream.write('call\\n')
        return 'Saved real-process response', {'input_tokens':10,'output_tokens':20,'usage_recorded':True}
    result, _ = await tracked_call(provider, model='test-model', system_prompt='System', user_content='Source',
                                   max_tokens=100,temperature=.2,json_mode=False)
    Path(sys.argv[2]).write_text('response committed')
    if sys.argv[1] == 'interrupt': await asyncio.sleep(120)
    async with AsyncSessionLocal() as db:
        await fence(db)
        gen = await db.get(Generation, UUID(run_id)); gen.status = GenerationStatus.COMPLETED
        db.add(Artifact(generation_id=gen.id,output_type='executive_summary',content=result,
                        review_status=ArtifactReviewStatus.PASSED))
        await db.commit()
async def main():
    await run_once('process-worker',pipeline=pipeline,lease_seconds=2)
    await engine.dispose()
asyncio.run(main())
''')
    env = {**os.environ, 'DATABASE_URL': test_engine.url.render_as_string(hide_password=False), 'APP_ENV':'test',
           'PYTHONPATH': str(__import__('pathlib').Path(__file__).resolve().parents[1])}
    def launch(mode):
        return subprocess.Popen([sys.executable, str(script), mode, str(marker), str(counter)], env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    first = launch('interrupt')
    try:
        for _ in range(200):
            if marker.exists(): break
            if first.poll() is not None: pytest.fail('First worker exited before checkpoint')
            await asyncio.sleep(.05)
        assert marker.exists(), 'Worker did not reach durable checkpoint'
    finally:
        first.kill(); await asyncio.to_thread(first.wait, timeout=10)
    async with session_factory() as db:
        await db.execute(update(DurableJob).where(DurableJob.generation_id == gid).values(
            lease_until=utcnow()-timedelta(seconds=1)))
        await db.commit()
    second = launch('finish')
    try:
        code = await asyncio.to_thread(second.wait, timeout=20)
        assert code == 0
    finally:
        if second.poll() is None: second.kill(); second.wait()
    assert counter.read_text().splitlines() == ['call']
    async with session_factory() as db:
        assert (await db.get(Generation, gid)).total_tokens == 30
        assert (await db.get(DurableJob, gid)).attempts == 2
        assert (await db.execute(select(Artifact))).scalar_one().content == 'Saved real-process response'


async def test_heartbeat_renews_loaded_sqlite_lease_during_long_task(session_factory):
    gid,_,_=await seed(session_factory)
    async def pipeline(_,run_id):
        # Multiple actual renewals exercise SQLAlchemy's loaded-row synchronization.
        await asyncio.sleep(1.2)
        async with session_factory() as db:
            generation=await db.get(Generation,gid)
            generation.status=GenerationStatus.COMPLETED
            await db.commit()
    assert await run_once('renewal-worker',session_factory,pipeline,lease_seconds=2)
    async with session_factory() as db:
        job=await db.get(DurableJob,gid)
        assert job.status=='completed' and job.attempts==1
        assert (await db.get(Generation,gid)).status==GenerationStatus.COMPLETED
