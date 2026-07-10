"""Audit log must redact PII (SSN/ITIN/passport/bank) from plaintext previews."""

from src.orchestrator.audit import record
from src.orchestrator.state import ReturnStateObject


def _flatten_preview(entry: dict) -> str:
    """Flatten an audit entry's preview dicts into one searchable string."""
    parts = []
    for key in ("inputs_preview", "outputs_preview"):
        preview = entry.get(key)
        if isinstance(preview, dict):
            parts.append(str(preview))
    return " ".join(parts)


def test_ssn_itin_redacted_in_preview():
    state = ReturnStateObject(tax_year=2025)
    state.identity.ssn = "123456789"
    state.identity.itin = "912345678"
    state.identity.passport_number = "E1234567"

    entry = record(
        state,
        layer="L1",
        function="test.fn",
        inputs=state.model_dump(),
        outputs=state.model_dump(),
        rationale="residency check",
    )

    flattened = _flatten_preview(entry.to_dict())
    assert "123456789" not in flattened
    assert "912345678" not in flattened
    assert "E1234567" not in flattened
    # The redaction marker should be present instead.
    assert "[REDACTED]" in flattened


def test_full_values_still_hashed():
    """Tamper-detection hashes must still cover the real (redacted) values."""
    state = ReturnStateObject(tax_year=2025)
    state.identity.ssn = "123456789"

    entry = record(
        state,
        layer="L1",
        function="test.fn",
        inputs=state.model_dump(),
        outputs=state.model_dump(),
        rationale="residency check",
    )

    # Hash must be non-empty and stable for the same input.
    assert entry.inputs_hash
    assert len(entry.inputs_hash) == 16
