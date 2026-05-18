"""Form 2210 — Underpayment of Estimated Tax (worst-case stub).

For v1 the populator surfaces the underpayment amount as a worst-case
penalty estimate; the IRS will compute the precise figure using §6621
rates and assessment timing.
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
    penalty = getattr(state, "estimated_tax_penalty", None) or {}

    return {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "tin": ident.primary_tin,
        "line_1_required_annual_payment": _fmt_money(state.tax.total_tax_liability),
        "line_6_total_withholding": _fmt_money(state.tax.total_withholding_credits),
        "line_7_underpayment": _fmt_money(max(0.0, float(state.tax.refund_or_owed))),
        "line_17_total_penalty": _fmt_money(penalty.get("penalty_amount", 0.0)),
        "_safe_harbor_met": penalty.get("safe_harbor_met", True),
        "_safe_harbor_reason": penalty.get("safe_harbor_reason", "Default safe harbor."),
    }
