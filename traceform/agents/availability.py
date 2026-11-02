"""Cached real inference check keyed by provider, model and credential revision."""
import asyncio
import hashlib
import time
from agents.llm import call_llm
from config.provider import current_configuration, create_configured_client
from db.session import AsyncSessionLocal
from orchestrator.progress import failure_guidance

_cached = None
_lock = asyncio.Lock()


async def provider_health(configuration=None):
    global _cached
    if configuration is None:
        async with AsyncSessionLocal() as db:
            configuration, _ = await current_configuration(db)
    key = (configuration.provider, configuration.model,
           hashlib.sha256((configuration.encrypted_key or "").encode()).hexdigest())
    async with _lock:
        if _cached and _cached[0] == key and time.monotonic() < _cached[1]:
            return _cached[2]
        client = None
        try:
            client = create_configured_client(configuration)
            if client is None:
                raise RuntimeError("API key not configured")
            await asyncio.wait_for(call_llm(client, configuration.model, "Reply with OK.",
                                           "Availability check.", max_tokens=128, strict=True), 65)
            result = {"available": True, "model": configuration.model, "message": "Ready to generate"}
        except Exception as exc:
            result = {"available": False, "model": configuration.model, "message": failure_guidance(exc)}
        finally:
            close = getattr(client, "close", None)
            if close:
                try:
                    closed = close()
                    if asyncio.iscoroutine(closed):
                        await closed
                except Exception:
                    pass
        _cached = (key, time.monotonic() + (60 if result["available"] else 10), result)
        return result
