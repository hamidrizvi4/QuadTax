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

    amti = float(amt.get("amti", 0.0) or 0.0)
    exemption = float(amt.get("exemption", 0.0) or 0.0)
    tmt = float(amt.get("tentative_minimum_tax", 0.0) or 0.0)
    regular_tax_for_amt = float(amt.get("regular_tax_for_amt", 0.0) or 0.0)

    # Real line 6 ("Subtract line 5 from line 4. If more than zero, go to
    # line 7. If zero or less, enter -0-...") isn't stored on AMTResult, but
    # it's fully derivable from amti/exemption already in state.amt — no
    # fabrication involved, just the same subtraction AMTCalculator performs
    # internally (and clamps to zero) before applying the 26%/28% kink.
    line_6_less_exemption = max(0.0, amti - exemption)

    # Real line 8 (AMT foreign tax credit) has no backing computation
    # anywhere in this engine (no Form 1116/AMT-FTC module) — left blank
    # rather than fabricated. Real line 9 ("Tentative minimum tax. Subtract
    # line 8 from line 7") therefore equals line 7 exactly (TMT minus a
    # blank/zero AMT FTC) — NOT the regular tax. Real line 10 ("regular tax"
    # per the line 10 worksheet, approximated here by 1040-NR line 16 /
    # eci_tax_liability) is where regular_tax_for_amt actually belongs.
    #
    # NOTE: this was previously swapped — regular_tax_for_amt was being
    # written to the printed line 9 (Tentative minimum tax) slot while
    # printed line 10 (regular tax) was left entirely blank, which both
    # mislabeled the value on line 9 and made the visible line 9/10/11 math
    # on the PDF fail to reconcile (11 = 9 − 10, but 10 was blank/0).
    line_9_tmt_after_ftc = tmt
    line_10_regular_tax = regular_tax_for_amt

    return {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "tin": ident.primary_tin,
        # Real PDF line 1b ("Subtract line 1a from ... line 11b"). Line 1a
        # (Schedule 1-A add-back) is intentionally left blank — this engine
        # has no Schedule 1-A intake, and NRA filers on the NRA path do not
        # get a standard deduction, so taxable_income is the correct line-1b
        # starting point without a 1a adjustment. Confirmed this still reads
        # state.tax.taxable_income (a taxable-income base), NOT a tax
        # liability dollar amount (regression-tested).
        "line_1_taxable_income": _fmt_money(state.tax.taxable_income),
        # Lines 2a-2t and 3 (AMT preference/adjustment items — e.g. the
        # Schedule A SALT deduction add-back, ISO exercise, depreciation,
        # private activity bond interest) are intentionally left blank.
        # AMTCalculator is a documented v1 simplification that always uses
        # preferences=0, so amti below already equals taxable_income with no
        # adjustments; populating individual 2a-2t fields without also
        # teaching AMTCalculator to fold them into `amti` would make the
        # printed "combine lines 1b through 3 -> line 4" math inconsistent
        # on the face of the form. Flagged as a known engine-level gap, not
        # fixed here (out of scope for form-field mapping; see amt_calculator.py).
        "line_4_amti": _fmt_money(amti),
        "line_5_exemption": _fmt_money(exemption),
        "line_6_less_exemption": _fmt_money(line_6_less_exemption),
        "line_7_tmt_before_credits": _fmt_money(tmt),
        # Line 8 (AMT foreign tax credit) intentionally left blank — no
        # AMT-specific FTC/Form 1116 computation exists anywhere in this
        # engine to source a real value from.
        "line_9_tmt_after_ftc": _fmt_money(line_9_tmt_after_ftc),
        "line_10_regular_tax": _fmt_money(line_10_regular_tax),
        "line_11_amt_owed": _fmt_money(amt.get("amt_owed", 0.0)),
        "_binds": amt.get("binds", False),
    }
