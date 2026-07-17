"""End-to-end API behavior for a filer requesting an unsupported tax year.

Complements ``tests/test_database/test_tax_year_loader.py::test_unknown_year_raises``
(which only proves the low-level ``load_year()`` function raises
``FileNotFoundError``) by proving the *real* HTTP path — POST
``/api/v1/submit`` -> ``TaxEngine.run_full_pipeline`` -> ``load_year`` — turns
that into a clean, well-typed, actionable 4xx response instead of the opaque
500 every other unhandled pipeline failure gets (see
``tests/test_api/test_error_handling.py``).

No LLM client mocking is required: the engine checks ``load_year(tax_year)``
before running L1 (the first layer that would otherwise call out to the
OpenAI client), so requesting an unsupported year never reaches the network.
That fail-fast behavior is asserted directly here too.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def _payload_for_year(tax_year: int) -> dict:
    payload = {
        "intake": {
            "identity": {"filing_status": "single"},
            "residency": {"tax_year": tax_year, "visa_type": "F-1"},
            "income": {},
        }
    }
    return payload


def test_submit_unsupported_tax_year_returns_clean_400():
    """TY2026 (unsupported today) must come back as a clean 400, not a 500."""
    r = client.post(
        "/api/v1/submit",
        json=_payload_for_year(2026),
        headers={"Authorization": "Bearer test-key-not-a-secret"},
    )

    assert r.status_code == 400
    body = r.json()
    detail = body["detail"]
    assert detail["error"] == "unsupported_tax_year"
    assert detail["requested_tax_year"] == 2026
    assert detail["supported_tax_years"] == [2025]
    # Actionable message, not an opaque "Reference: <id>" correlation string.
    assert "2026" in detail["message"]
    assert "2025" in detail["message"]
    assert "Reference:" not in str(detail)


def test_submit_unsupported_tax_year_never_calls_the_llm():
    """The unsupported-year check must fail fast, before any LLM call.

    If this regresses (e.g. the check moves after L1), a filer would burn a
    real OpenAI request extracting I-94 data for a year the engine can never
    actually compute a return for.
    """
    with patch("src.llm_config.get_openai_client") as mock_get_client:
        r = client.post(
            "/api/v1/submit",
            json=_payload_for_year(2026),
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 400
        mock_get_client.assert_not_called()


def test_submit_supported_tax_year_is_not_rejected_by_year_check():
    """Sanity check: TY2025 must not trip the unsupported-year path.

    Uses a deliberately-empty intake so the pipeline fails naturally further
    downstream (missing required OCR/MCQ context) rather than asserting a
    full successful filing here (covered by
    ``tests/test_integration/test_full_pipeline.py``). What matters for this
    test is that the response is NOT the unsupported_tax_year error.
    """
    r = client.post(
        "/api/v1/submit",
        json=_payload_for_year(2025),
        headers={"Authorization": "Bearer test-key-not-a-secret"},
    )
    if r.status_code == 400:
        assert r.json()["detail"].get("error") != "unsupported_tax_year"
