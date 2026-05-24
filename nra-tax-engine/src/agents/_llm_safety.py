"""LLM safety wrapper — schema-validated, temperature-pinned, optional dual-extract.

Every agent that calls a model routes through :func:`safe_parse`. The wrapper:

    * Forces ``temperature=0.0`` regardless of caller arguments.
    * Wraps the call in a try/except that surfaces extraction failures as
      ``ExtractionConfidenceError`` rather than silent crashes.
    * Optionally invokes a *secondary* client with a different model id and
      compares the parsed responses field-by-field on monetary / integer
      fields. On mismatch, the wrapper raises
      :class:`ExtractionConfidenceError` (which the orchestrator catches and
      routes into ``state.requires_human_review``).

The secondary extraction is opt-in: callers either pass a ``secondary_client``
+ ``secondary_model`` pair, or set ``QUADTAX_DUAL_EXTRACT=true`` in the
environment to enable a same-client/different-model second-opinion.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_DUAL_EXTRACT_ENV = "QUADTAX_DUAL_EXTRACT"


class ExtractionConfidenceError(RuntimeError):
    """Raised when primary and secondary LLM extractions disagree on monetary fields."""


@dataclass
class ExtractionMismatch:
    field: str
    primary: Any
    secondary: Any


def _is_numeric_field(name: str, value: Any) -> bool:
    """Heuristic: numeric box fields ('box_1_wages', 'days_current_year', ...) are critical."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    return False


def _close_enough(a: float, b: float, *, abs_tol: float = 1.0, rel_tol: float = 0.005) -> bool:
    """Two monetary values are 'close enough' when within $1 or 0.5%."""
    return math.isclose(float(a), float(b), abs_tol=abs_tol, rel_tol=rel_tol)


def _compare_models(
    primary: BaseModel,
    secondary: BaseModel,
    *,
    critical_fields: Optional[Iterable[str]] = None,
) -> list[ExtractionMismatch]:
    """Return the list of monetary / integer fields where the two parses disagree."""
    mismatches: list[ExtractionMismatch] = []
    p_data = primary.model_dump()
    s_data = secondary.model_dump()
    fields = set(critical_fields) if critical_fields else set(p_data.keys())
    for field_name in fields:
        if field_name not in p_data or field_name not in s_data:
            continue
        pv = p_data[field_name]
        sv = s_data[field_name]
        if not _is_numeric_field(field_name, pv) and not _is_numeric_field(field_name, sv):
            continue
        if isinstance(pv, bool) or isinstance(sv, bool):
            continue
        try:
            if not _close_enough(pv, sv):
                mismatches.append(ExtractionMismatch(field_name, pv, sv))
        except (TypeError, ValueError):
            if pv != sv:
                mismatches.append(ExtractionMismatch(field_name, pv, sv))
    return mismatches


def _invoke(
    client: Any,
    *,
    model: str,
    messages: list[dict],
    response_format: Type[T],
) -> T:
    """One LLM call. Always ``temperature=0.0``."""
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=response_format,
        temperature=0.0,
    )
    return completion.choices[0].message.parsed


def safe_parse(
    *,
    primary_client: Any,
    primary_model: str,
    messages: list[dict],
    response_format: Type[T],
    secondary_client: Any = None,
    secondary_model: Optional[str] = None,
    critical_fields: Optional[Iterable[str]] = None,
) -> T:
    """Run an LLM-as-OCR extraction with optional second-opinion verification.

    Args:
        primary_client: OpenAI-compatible client (must support
            ``.beta.chat.completions.parse``).
        primary_model: Model id for the primary extraction.
        messages: Standard chat-completion message list.
        response_format: Pydantic model the response is parsed into.
        secondary_client: Optional second client (different provider or model)
            used to cross-check critical numeric fields. When omitted and the
            ``QUADTAX_DUAL_EXTRACT`` env var is set, the primary client is
            re-called with a different model id ("gpt-4o-mini" or whatever the
            env var ``QUADTAX_SECONDARY_MODEL`` specifies).
        secondary_model: Model id for the secondary client.
        critical_fields: Iterable of field names to compare. When omitted,
            every numeric field on the parsed model is compared.

    Returns:
        The primary extraction.

    Raises:
        ExtractionConfidenceError: When secondary extraction is enabled and
            any monetary / integer field disagrees with the primary.
    """
    primary = _invoke(
        primary_client,
        model=primary_model,
        messages=messages,
        response_format=response_format,
    )

    # Resolve whether a second opinion should run.
    if secondary_client is None and os.environ.get(_DUAL_EXTRACT_ENV) == "true":
        secondary_client = primary_client
        secondary_model = secondary_model or os.environ.get(
            "QUADTAX_SECONDARY_MODEL", "gpt-4o-mini"
        )

    if secondary_client is None or secondary_model is None:
        return primary

    try:
        secondary = _invoke(
            secondary_client,
            model=secondary_model,
            messages=messages,
            response_format=response_format,
        )
    except Exception as exc:  # noqa: BLE001
        # A failed second opinion is itself a low-confidence signal; surface it.
        raise ExtractionConfidenceError(
            f"Secondary extraction ({secondary_model}) failed: {exc}"
        ) from exc

    mismatches = _compare_models(
        primary, secondary, critical_fields=critical_fields
    )
    if mismatches:
        details = "; ".join(
            f"{m.field}: primary={m.primary!r} vs secondary={m.secondary!r}"
            for m in mismatches
        )
        raise ExtractionConfidenceError(
            f"Dual-extract mismatch on {len(mismatches)} field(s) — {details}"
        )
    return primary
