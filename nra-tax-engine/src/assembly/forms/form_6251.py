"""Form 6251 — Alternative Minimum Tax (Individuals).

Attached when :class:`AMTCalculator` reports a non-zero AMT or when the
filer has AMT preferences that need disclosure regardless of amount.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def _fmt_money(value) -> str:
    if value in (None, ""):
        return ""
    try:
        rounded = round(float(value))
    except (TypeError, ValueError):
        return ""
    return "" if rounded == 0 else str(rounded)


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    amt = getattr(state, "amt", None) or {}

    return {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "tin": ident.primary_tin,
        "line_1_taxable_income": _fmt_money(state.tax.taxable_income),
        "line_4_amti": _fmt_money(amt.get("amti", 0.0)),
        "line_5_exemption": _fmt_money(amt.get("exemption", 0.0)),
        "line_7_tmt_before_credits": _fmt_money(amt.get("tentative_minimum_tax", 0.0)),
        "line_9_regular_tax": _fmt_money(amt.get("regular_tax_for_amt", 0.0)),
        "line_11_amt_owed": _fmt_money(amt.get("amt_owed", 0.0)),
        "_binds": amt.get("binds", False),
    }
