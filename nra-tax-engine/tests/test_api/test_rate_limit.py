"""Test per-IP rate limiting on the LLM-calling POST endpoints.

Each test here uses its own dedicated fake client IP (via
``TestClient(app, client=(host, port))``) so it exercises a private slowapi
counter bucket -- get_remote_address() keys purely off request.client.host,
and every other test module in this suite shares the default
``TestClient(app)`` host ("testclient"). Without this isolation, a test that
deliberately exhausts a 20/minute limit would poison that shared bucket for
the rest of the process-lifetime test session.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.orchestrator.engine import HumanReviewRequiredError

AUTH = {"Authorization": "Bearer test-key-not-a-secret"}


def _ocr_client(host: str) -> TestClient:
    return TestClient(app, client=(host, 12345))


def _submit_client(host: str) -> TestClient:
    return TestClient(app, client=(host, 12345))


def test_ocr_endpoint_enforces_per_ip_limit():
    client = _ocr_client("198.51.100.10")
    with patch("src.api.ocr_endpoint.DocumentExtractor") as mock_ext:
        mock_ext.return_value.extract_all.return_value = {
            "i94": None,
            "w2s": [],
            "form_1042s": [],
            "form_1099s": [],
        }
        statuses = []
        for _ in range(21):
            r = client.post(
                "/api/v1/ocr",
                data={"tax_year": "2025"},
                headers=AUTH,
            )
            statuses.append(r.status_code)

    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


def test_ocr_rate_limit_response_shape():
    client = _ocr_client("198.51.100.11")
    with patch("src.api.ocr_endpoint.DocumentExtractor") as mock_ext:
        mock_ext.return_value.extract_all.return_value = {
            "i94": None,
            "w2s": [],
            "form_1042s": [],
            "form_1099s": [],
        }
        for _ in range(20):
            client.post("/api/v1/ocr", data={"tax_year": "2025"}, headers=AUTH)
        r = client.post("/api/v1/ocr", data={"tax_year": "2025"}, headers=AUTH)

    assert r.status_code == 429
    assert "error" in r.json()
    assert "Rate limit" in r.json()["error"]


def test_submit_endpoint_enforces_per_ip_limit():
    client = _submit_client("198.51.100.20")
    payload = {
        "intake": {
            "identity": {"filing_status": "single"},
            "residency": {"tax_year": 2025, "visa_type": "F-1"},
            "income": {},
        }
    }
    # Fail fast inside the pipeline (rather than running the real 9-layer
    # engine 21 times) -- the rate limiter check happens before this mock is
    # ever invoked, so the call still counts as one "hit" per request either way.
    with patch(
        "src.api.main.TaxEngine.run_full_pipeline",
        side_effect=HumanReviewRequiredError(["stub"]),
    ):
        statuses = []
        for _ in range(21):
            r = client.post("/api/v1/submit", json=payload, headers=AUTH)
            statuses.append(r.status_code)

    assert statuses[:20] == [422] * 20
    assert statuses[20] == 429


def test_rate_limit_is_per_ip_not_global():
    """Two distinct client IPs each get their own independent 20/minute budget."""
    with patch("src.api.ocr_endpoint.DocumentExtractor") as mock_ext:
        mock_ext.return_value.extract_all.return_value = {
            "i94": None,
            "w2s": [],
            "form_1042s": [],
            "form_1099s": [],
        }
        client_a = _ocr_client("198.51.100.30")
        client_b = _ocr_client("198.51.100.31")

        for _ in range(20):
            r = client_a.post("/api/v1/ocr", data={"tax_year": "2025"}, headers=AUTH)
            assert r.status_code == 200
        # client_a is now exhausted...
        assert client_a.post("/api/v1/ocr", data={"tax_year": "2025"}, headers=AUTH).status_code == 429
        # ...but client_b, a different remote address, is unaffected.
        assert client_b.post("/api/v1/ocr", data={"tax_year": "2025"}, headers=AUTH).status_code == 200


def test_healthz_endpoint_is_not_rate_limited_even_under_shared_ip():
    """Sanity check against the same-key contention every other test module
    shares (default TestClient host 'testclient'): healthz must never 429."""
    client = TestClient(app)
    for _ in range(25):
        r = client.get("/api/v1/healthz")
        assert r.status_code != 429
