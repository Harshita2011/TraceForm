"""
# §6F / §6G / §7 — Security Hardening, Audit Trail & Secrets Detection Tests.
"""

import os
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from security.api_keys import OperatorRole, hash_api_key, resolve_operator_from_key, verify_api_key_hash
from security.rate_limiter import SlidingWindowRateLimiter


class TestApiKeySecurity:
    def test_sha256_hashing_and_verification(self):
        raw_key = "secret-token-key-12345"
        key_hash = hash_api_key(raw_key)
        assert len(key_hash) == 64
        assert verify_api_key_hash(raw_key, key_hash) is True
        assert verify_api_key_hash("wrong-token", key_hash) is False

    def test_resolve_operator_role_scoping(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "key_auditor:auditor_user:auditor,key_admin:admin_user:admin")
        ctx = resolve_operator_from_key("key_auditor")
        assert ctx is not None
        assert ctx.operator_id == "auditor_user"
        assert ctx.role == OperatorRole.AUDITOR

        admin_ctx = resolve_operator_from_key("key_admin")
        assert admin_ctx is not None
        assert admin_ctx.operator_id == "admin_user"
        assert admin_ctx.role == OperatorRole.ADMIN


class TestRateLimiter:
    def test_sliding_window_rate_limiter_exceeds(self):
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=2)
        key = "test_operator_1"

        allowed1, rem1, _ = limiter.is_allowed(key)
        allowed2, rem2, _ = limiter.is_allowed(key)
        allowed3, rem3, _ = limiter.is_allowed(key)
        allowed4, rem4, _ = limiter.is_allowed(key)

        assert allowed1 is True
        assert allowed2 is True
        assert allowed3 is True
        assert allowed4 is False  # Exceeded max 3 requests
        assert rem4 == 0


class TestAuditTrailAPI:
    @pytest.mark.asyncio
    async def test_get_audit_trail_endpoint(self, client: AsyncClient):
        response = await client.get("/api/v1/audit/trail", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestNoHardcodedSecrets:
    def test_repository_contains_no_exposed_api_keys(self):
        """
        §7 — Verify that no real API keys or sensitive secret string literals
        are committed in python files across the repository.
        """
        root_dir = Path(__file__).parent.parent
        forbidden_prefixes = ["sk-ant-api03-", "AIzaSy", "ghp_"]

        for py_file in root_dir.rglob("*.py"):
            if "venv" in str(py_file) or ".git" in str(py_file) or py_file.name == "test_security_audit_hardening.py":
                continue
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for prefix in forbidden_prefixes:
                    assert prefix not in content, f"Found forbidden secret prefix '{prefix}' in {py_file}"
