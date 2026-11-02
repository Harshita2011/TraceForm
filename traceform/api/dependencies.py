"""
# §3.11 API Dependencies — shared FastAPI dependencies for DB sessions and auth.
"""

import os
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from security.api_keys import hash_api_key, resolve_operator_from_key

_API_KEYS: set[str] = set(
    k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()
)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)],
) -> str:
    """
    §6F / §7 — Verify the X-API-Key header against SHA-256 hashes and resolve operator identity.
    Returns operator_id.
    """
    from teams.scope import identity
    if identity.get():return identity.get()['user_id']
    valid_keys = _API_KEYS or set(
        k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()
    )
    if not valid_keys:
        if os.getenv("APP_ENV") == "production":
            raise HTTPException(status_code=503, detail="Operator authentication is not configured.")
        # Dev mode: no keys configured — allow all requests
        return "dev-no-auth"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide a valid key in the X-API-Key header.",
        )

    # Check against plain keys or parsed operator mappings
    key_clean = api_key.strip()
    key_hash = hash_api_key(key_clean)

    is_valid = False
    for vk in valid_keys:
        clean_vk = vk.split(":")[0].strip()
        if hash_api_key(clean_vk) == key_hash:
            is_valid = True
            break

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide a valid key in the X-API-Key header.",
        )

    op_ctx = resolve_operator_from_key(key_clean)
    return op_ctx.operator_id if op_ctx else key_clean


# Type aliases for use in route signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentOperator = Annotated[str, Depends(verify_api_key)]


async def review_access(operator: CurrentOperator,
                        api_key: Annotated[str | None, Security(_api_key_header)]):
    from teams.scope import identity
    if identity.get():return identity.get()['role'] in {'owner','reviewer'}
    from security.api_keys import OperatorRole
    context = resolve_operator_from_key(api_key)
    return operator == 'dev-no-auth' or bool(context and context.role in {OperatorRole.ADMIN, OperatorRole.REVIEWER})


async def require_review_operator(operator: CurrentOperator, allowed: Annotated[bool, Depends(review_access)]):
    if not allowed:
        raise HTTPException(403, 'A reviewer or administrator role is required for compliance exceptions.')
    return operator


ReviewOperator = Annotated[str, Depends(require_review_operator)]


async def require_admin(operator: CurrentOperator,
                        api_key: Annotated[str | None, Security(_api_key_header)]):
    from teams.scope import identity
    if identity.get():
        if identity.get()['workspace_id']=='legacy' and identity.get()['role']=='owner':return operator
        raise HTTPException(403,'Provider settings are managed by the installation owner.')
    from security.api_keys import OperatorRole
    if operator == "dev-no-auth" and os.getenv("APP_ENV") != "production":
        return operator
    context = resolve_operator_from_key(api_key)
    if context is None or context.role != OperatorRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only an administrator can change provider settings.")
    return context.operator_id


CurrentAdmin = Annotated[str, Depends(require_admin)]
