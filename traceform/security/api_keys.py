import hashlib
import os
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class OperatorRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"


class OperatorContext(BaseModel):
    operator_id: str
    role: OperatorRole
    key_hash: str


def hash_api_key(raw_key: str) -> str:
    """Compute SHA-256 hash of API key for secure verification and storage."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def verify_api_key_hash(raw_key: str, hashed_key: str) -> bool:
    """Verify raw API key matches SHA-256 hash using constant-time comparison."""
    return hash_api_key(raw_key) == hashed_key


def resolve_operator_from_key(raw_key: Optional[str]) -> Optional[OperatorContext]:
    """
    §6F / §7 — Resolve operator identity and role from raw API key.
    Supports format: API_KEYS="key1:op1:role1,key2:op2:role2" or single keys.
    """
    if not raw_key:
        return None

    raw_key_clean = raw_key.strip()
    raw_env_keys = os.getenv("API_KEYS", "").strip()

    # Default dev fallback if no keys configured
    if not raw_env_keys:
        return OperatorContext(
            operator_id="dev-operator",
            role=OperatorRole.ADMIN,
            key_hash=hash_api_key(raw_key_clean),
        )

    # Parse configured keys
    for entry in raw_env_keys.split(","):
        entry = entry.strip()
        if not entry:
            continue

        parts = entry.split(":")
        k = parts[0].strip()
        op_id = parts[1].strip() if len(parts) > 1 else f"operator-{hash_api_key(k)[:12]}"
        role_str = parts[2].strip().lower() if len(parts) > 2 else "admin"

        try:
            role = OperatorRole(role_str)
        except ValueError:
            role = OperatorRole.ANALYST

        # Constant-time comparison
        if hash_api_key(raw_key_clean) == hash_api_key(k):
            return OperatorContext(
                operator_id=op_id,
                role=role,
                key_hash=hash_api_key(k),
            )

    return None
