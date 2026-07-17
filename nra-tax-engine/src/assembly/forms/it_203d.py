"""Form IT-203-D — Nonresident / Part-Year Resident Itemized Deductions.

Only attached when the federal Schedule A total is nonzero (mirrored by
``FormPopulator``/``l9_ny`` triggering, matching the same itemized-vs-
standard signal used for the federal Schedule A attach condition).

Line semantics (verified against the real 2025 IT-203-D, 15 numbered
lines, single Federal-Schedule-A-mirrored column — unlike IT-203, this
form has no separate NY-source column):

    Line 1  Medical/dental (fed Sch A line 4): not tracked — blank.
    Line 2  Taxes paid (fed Sch A line 9) = state_local_income_tax.
    Line 3  Interest paid (fed Sch A line 15): not tracked — blank.
    Line 4  Gifts to charity (fed Sch A line 19) = charitable_cash +
            charitable_noncash.
    Line 5  Casualty/theft losses (fed Sch A line 20) = casualty_disaster_loss.
    Line 6  Job expenses (fed Sch A line 27, TCJA-eliminated concept with no
            NRA Schedule A analogue): not tracked — blank.
    Line 7  Other misc deductions (fed Sch A line 28) = other_itemized —
            mirrors schedule_a.py's own "line_7_other_itemized" mapping of
            the same ``sch_a.other_itemized`` value on the federal NRA
            Schedule A, so this NY line-item breakdown actually reconciles
            with line 8's total instead of silently dropping this component.
    Line 8  = federal Schedule A line 29 total = sch_a.total.
    Line 9  NY disallows the federal SALT deduction — subtract back out
            the state/local income tax claimed on line 2/8.
    Line 10 = line 8 - line 9.
    Line 11 College tuition itemized deduction (from IT-203-B line 2):
            not tracked — blank (Schedule C isn't populated either).
    Line 12 Addition adjustments: not tracked — blank.
    Line 13 = line 10 + line 11 + line 12.
    Line 14 Itemized deduction adjustment (high-income phaseout): not
            modeled — blank (out of scope for this population).
    Line 15 New York State itemized deduction (final) = line 13 - line 14.
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

    salt = float(sch_a.get("state_local_income_tax", 0.0))
    charitable = float(sch_a.get("charitable_cash", 0.0)) + float(
        sch_a.get("charitable_noncash", 0.0)
    )
    casualty = float(sch_a.get("casualty_disaster_loss", 0.0))
    other_itemized = float(sch_a.get("other_itemized", 0.0))
    line_8_total = float(sch_a.get("total", 0.0))
    line_10 = max(0.0, line_8_total - salt)

    return {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "ssn": ident.primary_tin,
        "line_2_taxes_paid": _fmt_money(salt),
        "line_4_charity": _fmt_money(charitable),
        "line_5_casualty": _fmt_money(casualty),
        "line_7_other_itemized": _fmt_money(other_itemized),
        "line_8_total": _fmt_money(line_8_total),
        "line_9_salt_addback": _fmt_money(salt),
        "line_10": _fmt_money(line_10),
        "line_13": _fmt_money(line_10),
        "line_15_ny_itemized": _fmt_money(line_10),
        "_note": (
            "Mirrors the federal Schedule A total with NY's required SALT "
            "addback (line 9); NY-only allowances (mortgage interest, "
            "property tax — line 3 and the job-expense line 6) and the "
            "college tuition itemized deduction (line 11) have no "
            "supporting intake data and are left blank."
        ),
    }
