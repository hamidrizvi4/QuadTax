"""Audit log — records every state mutation made by an agent or calculator.

The orchestrator threads every state-mutating call through :func:`record`
which:

    * Appends a structured :class:`AuditEntry` to ``state.audit_trail``
      (a plain list of dicts so Pydantic can serialize it).
    * Optionally persists each entry as one line of JSONL to
      ``outputs/<filing_id>/audit.jsonl`` when ``QUADTAX_AUDIT_DIR`` is set
      in the environment.

The audit trail powers three downstream consumers:

    1. The "Why this number?" UI in the client (read each entry's
       ``rationale`` to explain a result).
    2. The IRS-notice response workflow (a CPA can prove which inputs
       drove which outputs).
    3. Post-mortem debugging of regressions caught by the validators.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject

logger = logging.getLogger(__name__)

_AUDIT_DIR_ENV = "QUADTAX_AUDIT_DIR"

# Field names that carry direct identifiers / financial account numbers. These
# must never be written to the audit log in plaintext — full values are hashed
# for tamper-detection, but the human-readable preview redacts them.
_PII_KEYS = {
    "ssn",
    "itin",
    "passport_number",
    "spouse_ssn_or_itin",
    "spouse_ssn",
    "spouse_itin",
    "routing_number",
    "account_number",
    "bank_account_number",
}


@dataclass
class AuditEntry:
    """One row in the audit log."""

    layer: str
    function: str
    timestamp: str
    inputs_hash: str
    outputs_hash: str
    rationale: str
    filing_id: Optional[str] = None
    inputs_preview: Optional[dict] = None
    outputs_preview: Optional[dict] = None
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _stable_hash(value: Any) -> str:
    """Deterministic SHA-256 over the JSON-serialized representation."""
    try:
        blob = json.dumps(value, sort_keys=True, default=_json_default)
    except (TypeError, ValueError):
        blob = repr(value)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _json_default(o: Any) -> Any:
    try:
        return float(o)
    except (TypeError, ValueError):
        return repr(o)


def _preview(value: Any, max_keys: int = 8) -> Optional[dict]:
    """Return a small dict snapshot of ``value`` suitable for inclusion in the entry.

    PII keys are redacted so SSN/ITIN/passport/bank details are never written
    to the audit log in plaintext. The full values are still hashed (see
    ``_stable_hash``) for tamper-detection.
    """
    if isinstance(value, dict):
        items = list(value.items())[:max_keys]
        return {
            k: "[REDACTED]" if k in _PII_KEYS else _shrink(v) for k, v in items
        }
    return None


def _shrink(value: Any) -> Any:
    """Truncate strings and lists so the audit entry stays compact."""
    if isinstance(value, str):
        return value if len(value) <= 80 else value[:77] + "..."
    if isinstance(value, list):
        return value[:5]
    if isinstance(value, dict):
        return _preview(value)
    return value


def record(
    state: "ReturnStateObject",
    *,
    layer: str,
    function: str,
    inputs: Any,
    outputs: Any,
    rationale: str,
    extras: Optional[dict] = None,
) -> AuditEntry:
    """Append an :class:`AuditEntry` to ``state.audit_trail`` and persist to JSONL.

    Args:
        state: Current return state object — the entry is appended to its
            ``audit_trail`` list.
        layer: Layer id (e.g. ``"L1"``, ``"L3"``, ``"L9"``).
        function: Symbol producing the mutation (e.g.
            ``"SubstantialPresenceCalculator.evaluate_residency"``).
        inputs: Arguments passed to the function. Hashed for tamper detection
            and a small preview is embedded in the entry.
        outputs: Return value from the function.
        rationale: Plain-English reason this mutation happened — surfaces in
            the "Why this number?" UI and the IRS-notice response.
        extras: Optional dict of additional metadata to record alongside.

    Returns:
        The appended :class:`AuditEntry`.
    """
    filing_id = getattr(state, "filing_id", None)
    entry = AuditEntry(
        layer=layer,
        function=function,
        timestamp=datetime.now(timezone.utc).isoformat(),
        inputs_hash=_stable_hash(inputs),
        outputs_hash=_stable_hash(outputs),
        rationale=rationale,
        filing_id=filing_id,
        inputs_preview=_preview(inputs),
        outputs_preview=_preview(outputs),
        extras=extras or {},
    )
    # Use a plain dict to keep ReturnStateObject Pydantic-friendly.
    state.audit_trail.append(entry.to_dict())

    audit_dir = os.environ.get(_AUDIT_DIR_ENV)
    if audit_dir:
        try:
            path = Path(audit_dir) / (filing_id or "default") / "audit.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), default=_json_default) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist audit entry to %s: %s", audit_dir, exc)

    return entry
