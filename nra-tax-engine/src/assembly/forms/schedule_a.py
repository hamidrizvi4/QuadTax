"""Schedule A (1040-NR) — NRA itemized deductions.

Reads the pre-computed totals from :attr:`ReturnStateObject.sch_a` (populated
by :func:`src.functions.sch_a_nra.compute_sch_a_nra`).
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
    sch_a = state.sch_a or {}

    return {
        "line_1a_state_local_income_tax": _fmt_money(sch_a.get("state_local_income_tax", 0.0)),
        "line_1b_salt_cap_bite_note": (
            f"SALT cap reduced total by ${sch_a.get('salt_cap_bite', 0.0):,.0f}"
            if float(sch_a.get("salt_cap_bite", 0.0) or 0.0) > 0
            else ""
        ),
        "line_2_cash_gifts": _fmt_money(sch_a.get("charitable_cash", 0.0)),
        "line_3_noncash_gifts": _fmt_money(sch_a.get("charitable_noncash", 0.0)),
        "line_4_carryover": _fmt_money(0.0),
        "line_5_total_gifts": _fmt_money(
            float(sch_a.get("charitable_cash", 0.0))
            + float(sch_a.get("charitable_noncash", 0.0))
        ),
        "line_6_casualty_disaster": _fmt_money(sch_a.get("casualty_disaster_loss", 0.0)),
        "line_7_other_itemized": _fmt_money(sch_a.get("other_itemized", 0.0)),
        "line_8_total_itemized": _fmt_money(sch_a.get("total", 0.0)),
        "_disallowed_items_warnings": sch_a.get("disallowed_items", []),
    }
