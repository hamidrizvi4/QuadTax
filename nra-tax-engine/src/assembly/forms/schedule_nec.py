"""Schedule NEC (1040-NR) — FDAP / Not Effectively Connected income.

Lays out the per-rate columns (10%, 15%, 30%, "Other rate") that taxed
NRA passive income flow into. For students this is usually empty or
contains only scholarship FDAP at the reduced 14% rate.
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
    income = state.income
    tax = state.tax
    residency = state.residency

    # Pre-tax FDAP for column allocation. F/J/M/Q scholarship → 14% column;
    # all other FDAP defaults to the 30% column unless a treaty rate applies.
    fdap_total = float(income.fdap_taxable_total)
    is_fjmq = residency.exempt_visa_type in {"F-1", "J-1", "M-1", "Q-1"}

    col_14 = fdap_total if is_fjmq and fdap_total > 0 else 0.0
    col_30 = fdap_total if not is_fjmq and fdap_total > 0 else 0.0
    col_other_rate = 0.0

    # Scholarship-fellowship line 12 is the most-used line for students.
    return {
        "line_1_dividends_30": "",
        "line_2_interest_30": "",
        "line_5_royalties_30": "",
        "line_8_gambling_30": "",
        "line_12_scholarship_14": _fmt_money(col_14),
        "line_12_scholarship_30": _fmt_money(col_30 if not is_fjmq else 0.0),
        "line_15_total_other_rate": _fmt_money(col_other_rate),
        "line_15a_total_10": "",
        "line_15b_total_15": "",
        "line_15c_total_30": _fmt_money(col_30),
        "line_15d_total_other_rate": _fmt_money(col_other_rate),
        "line_16_tax_total": _fmt_money(tax.fdap_tax_liability),
    }
