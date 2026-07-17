"""Test GET /api/v1/healthz reports real system state instead of a hardcoded 200.

Covers:
  * healthy: all three checks pass -> 200, status "ok".
  * degraded: QUADTAX_API_KEY unset -> 503.
  * degraded: QUADTAX_API_KEY still the .env.example placeholder -> 503.
  * degraded: OPENAI_API_KEY unset/empty -> 503.
  * degraded: vendored PDF templates directory missing/empty -> 503.
  * healthz is never rate-limited, regardless of how many times it's polled.
"""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app

client = TestClient(app)


def test_healthz_ok_when_everything_configured():
    """Baseline: conftest.py sets a real (non-placeholder) QUADTAX_API_KEY and
    OPENAI_API_KEY, and this checkout vendors assets/templates/2025/, so the
    default state is healthy."""
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"] == {
        "api_key_configured": True,
        "llm_api_key_configured": True,
        "templates_present": True,
    }


def test_healthz_degraded_when_api_key_unset():
    with patch.dict(os.environ, {"QUADTAX_API_KEY": ""}):
        r = client.get("/api/v1/healthz")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"
        assert body["checks"]["api_key_configured"] is False


def test_healthz_degraded_when_api_key_is_placeholder():
    with patch.dict(os.environ, {"QUADTAX_API_KEY": "change-me-to-a-long-random-secret"}):
        r = client.get("/api/v1/healthz")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"
        assert body["checks"]["api_key_configured"] is False


def test_healthz_degraded_when_llm_api_key_unset():
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        r = client.get("/api/v1/healthz")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"
        assert body["checks"]["llm_api_key_configured"] is False
        # The other checks must still be reported (and still passing).
        assert body["checks"]["api_key_configured"] is True


def test_healthz_degraded_when_templates_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "_templates_dir", lambda: tmp_path / "does-not-exist")
    r = client.get("/api/v1/healthz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["templates_present"] is False


def test_healthz_degraded_when_templates_dir_empty(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty_templates"
    empty_dir.mkdir()
    monkeypatch.setattr(main_module, "_templates_dir", lambda: empty_dir)
    r = client.get("/api/v1/healthz")
    assert r.status_code == 503
    assert r.json()["checks"]["templates_present"] is False


def test_healthz_never_rate_limited():
    """/healthz must stay usable for liveness probes no matter how often it's
    polled -- unlike /submit and /ocr it carries no @limiter.limit decorator."""
    for _ in range(30):
        r = client.get("/api/v1/healthz")
        assert r.status_code != 429
