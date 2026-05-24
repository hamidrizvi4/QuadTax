"""Form IT-203-B — Nonresident and Part-Year Resident Income Allocation.

Schedule A: allocation of wage and salary income to NY State.
Schedule B: living-quarters maintained in NY (drives the statutory-residency
            inquiry; the engine reports facts from intake).
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
    ny = state.ny

    return {
        # Identity
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "tin": ident.primary_tin,
        # Schedule A — Allocation of wages
        "sched_A_employer_name": "",  # intake-derived (first employer)
        "sched_A_employer_address": "",  # intake-derived
        "sched_A_total_wages_box_1": _fmt_money(state.income.total_w2_wages),
        "sched_A_total_days": 365,  # default; intake should override
        "sched_A_ny_workdays": 0,    # intake-derived
        "sched_A_workdays_outside_ny": 0,  # intake-derived
        "sched_A_holidays": 0,
        "sched_A_total_workdays_in_year": 0,
        "sched_A_ny_pct": (
            f"{ny.ny_income_percentage * 100:.4f}" if ny.ny_income_percentage else "0.0000"
        ),
        "sched_A_ny_source_wages": _fmt_money(ny.ny_source_wages),
        # Schedule B — Living quarters maintained in NY
        "sched_B_address_in_ny": ident.us_address_line1 if ny.days_in_ny else "",
        "sched_B_relationship": "self",
        "sched_B_did_you_maintain_abode_in_ny": (
            "Yes" if ny.residency_reason and "permanent abode" in ny.residency_reason else "No"
        ),
        "sched_B_months_maintained": 0,  # intake-derived
        "sched_B_days_in_ny": ny.days_in_ny,
    }
