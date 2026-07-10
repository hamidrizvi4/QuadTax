"""Test that internal error details are never leaked to API clients."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.orchestrator.state import ReturnStateObject

client = TestClient(app)


def test_submit_does_not_leak_internal_error():
    """A pipeline failure must return a generic message, not str(exc)."""
    dummy = ReturnStateObject(tax_year=2025)

    def boom(*args, **kwargs):
        raise RuntimeError("SECRET_PATH=/Users/foo/.env traceback leaked")

    with patch("src.api.main.TaxEngine.run_full_pipeline", side_effect=boom):
        payload = {
            "intake": {
                "identity": {"filing_status": "single"},
                "residency": {"tax_year": 2025, "visa_type": "F-1"},
                "income": {},
            }
        }
        r = client.post(
            "/api/v1/submit",
            json=payload,
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 500
        body = r.json()
        # The opaque reference must be present...
        assert "Reference:" in body["detail"]
        # ...and the secret internal text must NOT be in the response.
        assert "SECRET_PATH" not in body["detail"]
        assert "traceback" not in body["detail"].lower()
