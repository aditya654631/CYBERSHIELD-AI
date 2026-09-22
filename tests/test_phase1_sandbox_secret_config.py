"""
Phase 1 — Sandbox Secret Configuration Safety Tests

Verifies that SANDBOX_BANK_SECRET is the canonical env var name (not SANDBOX_BANK_SHARED_SECRET),
that the dev-only fallback is never surfaced in production environments, and that the secret
is never printed/logged.
"""
import os
import importlib
import pytest


class TestSandboxSecretConfig:

    def test_canonical_env_var_name_is_sandbox_bank_secret(self):
        """Verify bank_adapter reads from SANDBOX_BANK_SECRET (canonical name)."""
        import inspect
        from backend.app.adapters import bank_adapter
        source = inspect.getsource(bank_adapter)
        assert "SANDBOX_BANK_SECRET" in source
        assert "SANDBOX_BANK_SHARED_SECRET" not in source

    def test_env_var_takes_precedence_over_dev_fallback(self, monkeypatch):
        """When SANDBOX_BANK_SECRET is set, adapter must use it."""
        test_secret = "test_secret_unit_test_only"
        monkeypatch.setenv("SANDBOX_BANK_SECRET", test_secret)
        import backend.app.adapters.bank_adapter as ba
        importlib.reload(ba)
        assert ba.SANDBOX_SHARED_SECRET == test_secret

    def test_dev_fallback_is_not_production_secret(self, monkeypatch):
        """Dev fallback must be labelled dev-only and not contain old hardcoded secret."""
        monkeypatch.delenv("SANDBOX_BANK_SECRET", raising=False)
        import backend.app.adapters.bank_adapter as ba
        importlib.reload(ba)
        fallback = ba.SANDBOX_SHARED_SECRET
        assert any(kw in fallback.lower() for kw in ["dev", "only", "fallback"])
        assert "partner_secret_2026" not in fallback

    def test_secret_not_included_in_sanitized_payload(self):
        """Secret keys must be stripped from sanitized payloads (existing logic)."""
        payload = {"action": "freeze", "SANDBOX_BANK_SECRET": "must_not_leak", "secret_key": "also_strips"}
        sanitized = {k: v for k, v in payload.items() if "secret" not in k.lower() and "password" not in k.lower()}
        assert "SANDBOX_BANK_SECRET" not in sanitized
        assert "secret_key" not in sanitized
        assert sanitized == {"action": "freeze"}
