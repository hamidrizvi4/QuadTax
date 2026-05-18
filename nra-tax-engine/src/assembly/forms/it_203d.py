"""Form IT-203-D — Nonresident / Part-Year Resident Itemized Deductions.

For v1 we default to the NY standard deduction; this populator is included
so that a future intake extension capturing NY-specific itemized data can
flip the deduction path without code changes elsewhere.
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
    sch_a = state.sch_a or {}

    return {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "tin": ident.primary_tin,
        # NY itemized broadly tracks federal Schedule A but allows mortgage
        # interest and property tax. v1 mirrors the federal Sch A totals and
        # surfaces a note when the filer has NY-only itemized items that need
        # human verification.
        "line_1_medical_dental": "",
        "line_5_state_local_taxes": _fmt_money(sch_a.get("state_local_income_tax", 0.0)),
        "line_8_real_estate_tax": "",  # NY itemized allows; intake-derived
        "line_9_mortgage_interest": "",  # NY itemized allows; intake-derived
        "line_13_charitable_cash": _fmt_money(sch_a.get("charitable_cash", 0.0)),
        "line_14_charitable_noncash": _fmt_money(sch_a.get("charitable_noncash", 0.0)),
        "line_18_casualty_loss": _fmt_money(sch_a.get("casualty_disaster_loss", 0.0)),
        "line_21_total_itemized": _fmt_money(sch_a.get("total", 0.0)),
        "_note": (
            "NY itemized deductions allow mortgage interest and property tax "
            "that the federal NRA Schedule A disallows. v1 mirrors the federal "
            "Schedule A total; populate the NY-only lines via an intake extension."
        ),
    }
