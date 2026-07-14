"""Schedule NEC (1040-NR) — FDAP / Not Effectively Connected income.

Lays out the per-rate columns (10%, 15%, 30%, "Other rate") that taxed
NRA passive income flow into. For students this is usually empty or
contains only scholarship FDAP at the reduced 14% withholding rate under
§1441(b) — the vendored 2025 revision of this PDF has no dedicated 14%
rate column, so that amount is written into the "Other rate" column
instead (see line_12_scholarship_other_rate below).

Key names below match the line numbers actually printed on the vendored
PDF (confirmed against assets/templates/2025/f1040nrn_fields.json's
AcroForm hierarchy, e.g. "...Line11[0]..." for gambling) — NOT a generic
guess at Schedule NEC's layout. Earlier revisions of this file used
different line numbers for several of these (dividends/interest/royalties/
gambling/totals) that didn't match this year's actual form; if the IRS
reflows the form in a future year, re-verify against the new PDF's own
field-name hierarchy rather than trusting these numbers to still be right.
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

    # Pre-tax FDAP for column allocation. F/J/M/Q scholarship → "Other rate"
    # column (this form has no dedicated 14% column); all other FDAP
    # defaults to the 30% column unless a treaty rate applies.
    fdap_total = float(income.fdap_taxable_total)
    is_fjmq = residency.exempt_visa_type in {"F-1", "J-1", "M-1", "Q-1"}

    col_other_rate = fdap_total if is_fjmq and fdap_total > 0 else 0.0
    col_30 = fdap_total if not is_fjmq and fdap_total > 0 else 0.0

    # Line 12 "Other (specify)" is the most-used line for student scholarship FDAP.
    return {
        "line_1a_dividends_30": "",
        "line_2c_interest_30": "",
        "line_5_royalties_30": "",
        "line_11_gambling_30": "",
        "line_12_scholarship_other_rate": _fmt_money(col_other_rate),
        "line_12_scholarship_30": _fmt_money(col_30 if not is_fjmq else 0.0),
        "line_13_subtotal_other_rate": _fmt_money(col_other_rate),
        "line_14_tax_10": "",
        "line_14_tax_15": "",
        "line_14_tax_30": _fmt_money(col_30),
        "line_14_tax_other_rate": _fmt_money(col_other_rate),
        "line_15_tax_total": _fmt_money(tax.fdap_tax_liability),
    }
