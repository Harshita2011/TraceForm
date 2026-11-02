"""Behavioral coverage for truthful progress, retry recovery, and provider preflight."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select

from db.models import Generation, Source, Artifact, PipelineEvent
from schemas.enums import GenerationStatus, ArtifactReviewStatus, SensitivityLevel, SensitivitySource
from orchestrator.progress import read_progress, failure_guidance


async def make_run(db):
    source = Source(extracted_text="A factual source passage.", sensitivity=SensitivityLevel.INTERNAL,
                    sensitivity_source=SensitivitySource.OPERATOR, sensitivity_confidence=1)
    db.add(source)
    await db.flush()
    run = Generation(source_id=source.id, output_types=["executive_summary", "research_report"],
                     params={"tone": "formal", "audience": "technical"}, status=GenerationStatus.FAILED,
                     budget_type="tokens", budget_ceiling=50000)
    db.add(run)
    await db.commit()
    return run


async def test_progress_does_not_mark_future_stages_failed(db_session):
    run = await make_run(db_session)
    db_session.add_all([PipelineEvent(generation_id=run.id, stage="extract", status="running"),
                        PipelineEvent(generation_id=run.id, stage="extract", status="failed", message="Provider is busy")])
    await db_session.commit()
    result = await read_progress(db_session, run)
    assert [(s["name"], s["status"]) for s in result["stages"]] == [
        ("ingest", "done"), ("extract", "failed"), ("generate", "queued"), ("review", "queued"), ("deliver", "queued")]
    assert result["error"] == "Provider is busy"


async def test_parallel_progress_waits_for_all_outputs(db_session):
    run = await make_run(db_session)
    run.status = GenerationStatus.RUNNING
    db_session.add(PipelineEvent(generation_id=run.id, stage="generate", status="done", output_type="executive_summary"))
    await db_session.commit()
    result = await read_progress(db_session, run)
    assert next(s for s in result["stages"] if s["name"] == "generate")["status"] == "running"
    assert next(s for s in result["stages"] if s["name"] == "review")["status"] == "queued"


async def test_recovered_stage_does_not_keep_an_old_error(db_session):
    run = await make_run(db_session)
    run.status = GenerationStatus.RUNNING
    db_session.add(PipelineEvent(generation_id=run.id, stage="extract", status="failed", message="Temporary failure"))
    await db_session.commit()
    db_session.add(PipelineEvent(generation_id=run.id, stage="extract", status="done"))
    await db_session.commit()
    assert (await read_progress(db_session, run))["error"] is None


async def test_retry_preserves_settings_and_skips_passed_outputs(client, db_session):
    run = await make_run(db_session)
    db_session.add(Artifact(generation_id=run.id, output_type="executive_summary", content="Passed output", review_status=ArtifactReviewStatus.PASSED))
    await db_session.commit()
    with patch("api.routes.generations.enqueue_generation", return_value="task-id"):
        response = await client.post(f"/api/v1/generations/{run.id}/retry")
    assert response.status_code == 202
    created = await db_session.get(Generation, UUID(response.json()["id"]))
    assert created.id != run.id
    assert created.source_id == run.source_id
    assert created.params["tone"] == "formal"
    assert created.output_types == ["research_report"]
    assert created.budget_ceiling == 50000


async def test_retry_rejects_running_generation(client, db_session):
    run = await make_run(db_session)
    run.status = GenerationStatus.RUNNING
    await db_session.commit()
    assert (await client.post(f"/api/v1/generations/{run.id}/retry")).status_code == 409


async def test_unavailable_provider_does_not_create_new_run(client, db_session, monkeypatch):
    run = await make_run(db_session)
    async def unavailable(configuration=None): return {"available": False, "message": "Provider temporarily busy"}
    monkeypatch.setattr("agents.availability.provider_health", unavailable)
    response = await client.post('/api/v1/generations/', json={"source_id": str(run.source_id), "output_types": ["executive_summary"]})
    assert response.status_code == 503
    assert response.json()["detail"] == "Provider temporarily busy"
    assert len((await db_session.execute(select(Generation))).scalars().all()) == 1


async def test_source_reference_endpoint_returns_actual_text(client, db_session):
    run = await make_run(db_session)
    response = await client.get(f"/api/v1/sources/{run.source_id}/text")
    assert response.status_code == 200
    assert response.json()["text"] == "A factual source passage."


async def test_temporary_provider_failure_retries_without_changing_model(monkeypatch):
    from agents.llm import call_llm
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")
    class BusyError(Exception): code = 503
    attempts = []
    def generate_content(**kwargs):
        attempts.append(kwargs["model"])
        if len(attempts) < 3: raise BusyError("busy")
        return SimpleNamespace(text="Actual output", usage_metadata=None)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        text, _ = await call_llm(SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)), "chosen-model", "System", "Source")
    assert text == "Actual output"
    assert attempts == ["chosen-model"] * 3


def test_failure_guidance_follows_provider_cause_without_exposing_raw_error():
    try:
        try: raise RuntimeError("503 high demand; secret-context")
        except RuntimeError as exc: raise RuntimeError("LLM unavailable") from exc
    except RuntimeError as exc:
        message = failure_guidance(exc)
    assert "temporarily busy" in message
    assert "secret-context" not in message


async def test_new_version_keeps_original_and_limits_requested_format(client, db_session):
    run = await make_run(db_session)
    run.status = GenerationStatus.COMPLETED
    await db_session.commit()
    with patch("api.routes.generations.enqueue_generation", return_value="task-id"):
        response = await client.post(f"/api/v1/generations/{run.id}/regenerate?output_type=research_report")
    assert response.status_code == 202
    new_run = await db_session.get(Generation, UUID(response.json()["id"]))
    assert new_run.id != run.id
    assert new_run.output_types == ["research_report"]
    assert run.status == GenerationStatus.COMPLETED
    assert new_run.params["audience"] == "technical"


async def test_review_exception_records_the_active_stage(session_factory):
    from orchestrator.jobs import _async_run_generator_task
    async with session_factory() as db:
        run = await make_run(db)
        db.add(PipelineEvent(generation_id=run.id, stage="review", status="running", output_type="research_report"))
        await db.commit()
    with patch("orchestrator.jobs.AsyncSessionLocal", session_factory), patch(
        "orchestrator.jobs._async_generate_output", side_effect=RuntimeError("503 busy")
    ):
        await _async_run_generator_task(None, str(run.id), str(run.id), "research_report", "model", 0)
    async with session_factory() as db:
        progress = await read_progress(db, run)
        artifacts = (await db.execute(select(Artifact).where(Artifact.generation_id == run.id))).scalars().all()
    assert next(s for s in progress["stages"] if s["name"] == "review")["status"] == "failed"
    assert next(s for s in progress["stages"] if s["name"] == "deliver")["status"] == "queued"
    assert artifacts[0].review_status == ArtifactReviewStatus.FAILED


async def test_successful_availability_check_is_cached(monkeypatch):
    import agents.availability as availability
    monkeypatch.setattr(availability, "_cached", None)
    monkeypatch.setattr(availability, "create_configured_client", lambda config: object())
    call = AsyncMock(return_value=("OK", {}))
    monkeypatch.setattr(availability, "call_llm", call)
    config = SimpleNamespace(provider="gemini", model="chosen", encrypted_key="fixture")
    first = await availability.provider_health(config)
    second = await availability.provider_health(config)
    assert first["available"] and second["available"]
    assert call.await_count == 1
