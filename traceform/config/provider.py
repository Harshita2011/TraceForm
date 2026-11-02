"""Versioned server-owned provider configuration, shared by API and independent workers."""
import os
from sqlalchemy.exc import IntegrityError
from db.models import ActiveProvider, ProviderConfiguration
from security.credentials import encrypt_key, decrypt_key


def environment_configuration():
    provider = "gemini" if os.getenv("GEMINI_API_KEY", "").strip() else "anthropic"
    from cost.tracker import load_pricing_config
    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite") if provider == "gemini" else os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    table = load_pricing_config()
    rates = table.get(model, table["default"])
    return ProviderConfiguration(provider=provider, model=model,
        encrypted_key=encrypt_key(os.getenv("GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY", "").strip()),
        pricing={**rates, "origin": "configured_table" if model in table else "fallback_estimate", "version": "initial"},
        created_by="environment")


async def current_configuration(db):
    active = await db.get(ActiveProvider, 1)
    if not active:
        config = environment_configuration()
        db.add(config)
        await db.flush()
        db.add(ActiveProvider(id=1, configuration_id=config.id, revision=1))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        active = await db.get(ActiveProvider, 1)
    return await db.get(ProviderConfiguration, active.configuration_id), active.revision


def public_configuration(config, revision):
    return {"revision": revision, "provider": config.provider, "model": config.model,
            "key_configured": bool(config.encrypted_key), "pricing": config.pricing,
            "applies_to": "New runs only. Queued and running jobs keep their saved configuration."}


def create_configured_client(config):
    key = decrypt_key(config.encrypted_key)
    if not key:
        return None
    if config.provider == "gemini":
        from google import genai
        return genai.Client(api_key=key, http_options={"timeout": 60000, "retry_options": {"attempts": 1}})
    import anthropic
    return anthropic.AsyncAnthropic(api_key=key, timeout=60, max_retries=0)
