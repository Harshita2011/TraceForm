"""Administrator-only changes; no endpoint ever returns a provider credential."""
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr, model_validator
from sqlalchemy import select, update
from api.dependencies import CurrentOperator, CurrentAdmin, DbSession
from config.provider import current_configuration, public_configuration
from db.models import ActiveProvider, ProviderConfiguration, WorkerState
from security.credentials import encrypt_key
from orchestrator.runtime import utcnow

router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    provider: Literal["gemini", "anthropic"]
    model: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9._:/-]+$")
    api_key: SecretStr | None = None
    clear_key: bool = False
    input_per_million: float = Field(ge=0, le=10000, allow_inf_nan=False)
    output_per_million: float = Field(ge=0, le=10000, allow_inf_nan=False)

    @model_validator(mode="after")
    def one_key_action(self):
        if self.clear_key and self.api_key and self.api_key.get_secret_value().strip():
            raise ValueError("Choose either a replacement key or removal, not both")
        return self


async def candidate_configuration(request, db, operator):
    current, revision = await current_configuration(db)
    if request.expected_revision != revision:
        raise HTTPException(status_code=409, detail="Settings changed in another session. Reload before saving.")
    supplied = request.api_key.get_secret_value().strip() if request.api_key else ""
    encrypted = (None if request.clear_key else encrypt_key(supplied) if supplied else
                 current.encrypted_key if request.provider == current.provider else None)
    return ProviderConfiguration(id=uuid4(), provider=request.provider, model=request.model,
        encrypted_key=encrypted, pricing={"input": request.input_per_million, "output": request.output_per_million,
        "origin": "operator_estimate", "version": uuid4().hex}, created_by=operator)


@router.get("/provider")
async def get_provider(request: Request, db: DbSession, operator: CurrentOperator):
    config, revision = await current_configuration(db)
    latest_worker = (await db.execute(select(WorkerState.last_seen_at).order_by(
        WorkerState.last_seen_at.desc()).limit(1))).scalar_one_or_none()
    from orchestrator.runtime import aware
    result = public_configuration(config, revision)
    from security.api_keys import resolve_operator_from_key, OperatorRole
    context = resolve_operator_from_key(request.headers.get("X-API-Key"))
    result["can_edit"] = operator == "dev-no-auth" or bool(context and context.role == OperatorRole.ADMIN)
    result["worker_online"] = bool(latest_worker and (utcnow() - aware(latest_worker)).total_seconds() < 30)
    return result


@router.post("/provider/models")
async def list_models(request: ProviderUpdate, db: DbSession, operator: CurrentAdmin):
    import asyncio
    import inspect
    from config.provider import create_configured_client
    config = await candidate_configuration(request, db, operator)
    if not config.encrypted_key:
        raise HTTPException(status_code=422, detail="Enter a provider key before loading models.")
    client = create_configured_client(config)
    try:
        if config.provider == "gemini":
            def discover():
                return [{"id": m.name.removeprefix("models/"), "name": m.display_name or m.name}
                        for m in client.models.list()
                        if "generateContent" in (m.supported_actions or [])]
            models = await asyncio.wait_for(asyncio.to_thread(discover), 20)
        else:
            page = await asyncio.wait_for(client.models.list(limit=100), 20)
            models = [{"id": m.id, "name": m.display_name} for m in page.data]
        return {"models": models}
    except Exception:
        raise HTTPException(status_code=422, detail="Could not load models. Check the provider key and connection, or enter a model ID manually.")
    finally:
        close = getattr(client, "close", None)
        if close:
            result = close()
            if inspect.isawaitable(result):
                await result


@router.post("/provider/test")
async def test_provider(request: ProviderUpdate, db: DbSession, operator: CurrentAdmin):
    from agents.availability import provider_health
    config = await candidate_configuration(request, db, operator)
    return await provider_health(config)


@router.put("/provider")
async def save_provider(request: ProviderUpdate, db: DbSession, operator: CurrentAdmin):
    from agents.availability import provider_health
    config = await candidate_configuration(request, db, operator)
    if config.encrypted_key:
        health = await provider_health(config)
        if not health["available"]:
            raise HTTPException(status_code=422, detail=health["message"])
    db.add(config)
    await db.flush()
    updated = await db.execute(update(ActiveProvider).where(ActiveProvider.id == 1,
        ActiveProvider.revision == request.expected_revision).values(configuration_id=config.id,
        revision=request.expected_revision + 1))
    if not updated.rowcount:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Settings changed in another session. Reload before saving.")
    await db.commit()
    return public_configuration(config, request.expected_revision + 1)
