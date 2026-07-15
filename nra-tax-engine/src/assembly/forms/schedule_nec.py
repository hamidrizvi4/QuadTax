"""Schedule NEC (1040-NR) — FDAP / Not Effectively Connected income.

Lays out the per-rate columns the vendored TY2025 PDF actually has —
confirmed by dumping the real widget annotations (walking each field's
``/Parent`` chain for the fully-qualified AcroForm name) and cross-checking
against the printed "Nature of Income" table via a position-sorted text
extraction, then visually re-confirmed by rendering the page to an image:

    (a) 10%   (b) 15%   (c) 30%   (d) Other (specify) — two independent
    sub-columns, each with its own "___%" rate blank at the top of the
    column (``Header[0].f1_3[0]`` / ``f1_4[0]``) that the preparer fills in
    once and which then applies to every dollar entered in that sub-column
    all the way down the table.

Every line (1a-12) has 5 value boxes in that same left-to-right order
(confirmed field x-coordinates: ~396/468/540/612/684pt). Lines 10c/11
(gambling) grey out some of those boxes on the real PDF (verified via
pixel sampling of the rendered page, not just the field list) — this
module never writes to a shaded box.

For students this form is usually empty or contains only scholarship FDAP
at the reduced 14% withholding rate under §1441(b) — routed into the
first "Other (specify)" sub-column with "14" written into that column's
rate blank, since this form has no dedicated 14% column.

Key names below match the line numbers actually printed on the vendored
PDF (confirmed against assets/templates/2025/f1040nrn_fields.json's
AcroForm hierarchy, e.g. "...Line11[0]..." for gambling) — NOT a generic
guess at Schedule NEC's layout. Earlier revisions of this file used
different line numbers for several of these (dividends/interest/royalties/
gambling/totals) that didn't match this year's actual form; if the IRS
reflows the form in a future year, re-verify against the new PDF's own
field-name hierarchy rather than trusting these numbers to still be right.

KNOWN LIMITATION (not fixable from within this module): lines 1a-11
(dividends, interest, industrial/motion-picture/other royalties, real
property income, pensions, social security, gambling) and Part II
(lines 16-18, capital gains/losses from property sales) are always left
blank here, even when the filer plausibly has FDAP in one of those
categories. This is a real gap, but the root cause is upstream: L3's
IncomeCodeMapper (src/functions/code_mapper.py) DOES know the 1042-S
income code per entry (dividend vs royalty vs gambling vs ...), but
l3_income.py immediately collapses every FDAP entry into one lump
``IncomeState.fdap_taxable_total`` float (see its ``routed_fdap``
accumulator) — the category is discarded before it ever reaches state,
and no capital-gain/property-sale data is captured anywhere in the state
model at all. Fixing this properly requires plumbing a per-category FDAP
breakdown through L3/IncomeState, not a change to this form module.
Fabricating a category here (e.g. guessing "dividends" for all FDAP)
would misstate a real tax form, so those lines stay blank instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject

# F/J/M/Q visa holders get the reduced 14% §1441(b) scholarship rate on
# FDAP (mirrors l6_tax_calc.py's own rate determination); everyone else
# gets the 30% statutory default. This form has no 10%/15% column use case
# reachable from current state data (nothing in IncomeState maps to those
# rates), so lines 14a/14b are always left blank.
_FJMQ_VISAS = {"F-1", "J-1", "M-1", "Q-1"}
_FJMQ_RATE = 0.14
_DEFAULT_RATE = 0.30


def _fmt_money(value) -> str:
    if value in (None, ""):
        return ""
    try:
        rounded = round(float(value))
    except (TypeError, ValueError):
        return ""
    return "" if rounded == 0 else str(rounded)


def _full_name(ident) -> str:
    parts = [ident.first_name, ident.middle_initial, ident.last_name, ident.suffix]
    return " ".join(p for p in parts if p)


def compute_field_map(state: "ReturnStateObject") -> dict:
    income = state.income
    tax = state.tax
    residency = state.residency
    ident = state.identity

    is_fjmq = residency.exempt_visa_type in _FJMQ_VISAS
    rate = _FJMQ_RATE if is_fjmq else _DEFAULT_RATE

    # tax.fdap_tax_liability is the single authoritative FDAP tax figure:
    # it's computed NET of any treaty exemption by l6_tax_calc.py, and
    # form_1040nr.py writes this exact same state field to 1040-NR line
    # 23a. Schedule NEC line 15's own instructions say "enter the total
    # here and on Form 1040-NR, line 23a" — so line 15 here and 1040-NR's
    # line 23a must always agree, which is only guaranteed by reading the
    # same state field rather than re-deriving a total from the columns.
    fdap_tax = float(tax.fdap_tax_liability)

    # income.fdap_taxable_total is the GROSS pre-treaty 1042-S FDAP total
    # (set once by L3 as `routed_fdap`); when a treaty exempts part of it
    # (e.g. China Art 20(b) on scholarship), l6_tax_calc.py nets it down
    # to `net_fdap` before multiplying by `rate` to get fdap_tax, but never
    # writes that net figure back onto state anywhere. Using the gross
    # total here (as this module previously did) would overstate the
    # income entered on lines 12/13 relative to the tax actually owed on
    # line 14/15, and the two would silently disagree once any partial
    # treaty exemption applies. Back-deriving the net amount from the
    # authoritative tax figure (net = tax / rate) recovers the correct
    # on-form income amount using only state that already exists, without
    # re-implementing L6's treaty-category bucketing logic here. When
    # fdap_tax is 0 (no FDAP at all, or fully treaty-exempt) this
    # correctly yields 0 regardless of which rate bucket would apply.
    net_fdap = (fdap_tax / rate) if fdap_tax > 0 else 0.0

    col_other_rate = net_fdap if is_fjmq else 0.0
    col_30 = net_fdap if not is_fjmq else 0.0

    if col_other_rate > 0:
        line_12_specify = "Scholarship/fellowship grant income (IRC §1441(b))"
        other_rate_pct = str(int(round(_FJMQ_RATE * 100)))  # "14"
    elif col_30 > 0:
        # Non-F/J/M/Q FDAP with no more specific category available (see
        # module docstring) — still statutorily taxed at 30%, which is
        # the form's own printed column (c) header, so no custom rate
        # blank needs to be filled in for this branch.
        line_12_specify = "Other FDAP income"
        other_rate_pct = ""
    else:
        line_12_specify = ""
        other_rate_pct = ""

    return {
        # Header — every attached schedule must repeat the filer's name
        # and identifying number. Verified against the real PDF: f1_1[0]
        # / f1_2[0] at the top of this AcroForm are the same header slots
        # schedule_oi.py already fills on Schedule OI's copy of this
        # hierarchy (form1040-NR[0].Page1[0].f1_1[0]/f1_2[0]); this form
        # was missing them entirely.
        "header_name": _full_name(ident),
        "header_identifying_number": ident.primary_tin,
        # Lines 1a-11: see module docstring — no per-category FDAP
        # breakdown exists in state, so these are genuinely un-fixable
        # from here and are left blank rather than guessing a category.
        "line_1a_dividends_30": "",
        "line_2c_interest_30": "",
        "line_5_royalties_30": "",
        "line_11_gambling_30": "",
        # Line 12 "Other (specify)" is the only bucket this engine's state
        # model can actually populate — everything not otherwise
        # categorized lands here. F/J/M/Q scholarship (14% under
        # §1441(b)) uses column (d)'s first "Other" sub-column (this form
        # has no dedicated 14% column); non-F/J/M/Q FDAP defaults to the
        # statutory 30% column (c).
        "line_12_other_specify": line_12_specify,
        "line_12_scholarship_other_rate": _fmt_money(col_other_rate),
        "line_12_scholarship_30": _fmt_money(col_30),
        # (d) column header "___%" blank for the first "Other" sub-column.
        # Must be filled whenever that sub-column carries a dollar amount
        # or the amount is unexplained. The second "Other" sub-column
        # (Header[0].f1_4[0]) has no corresponding data bucket in this
        # engine (there is no second uncategorized-FDAP rate) and is
        # intentionally left unmapped.
        "line_hdr_other_rate_pct": other_rate_pct,
        "line_13_subtotal_other_rate": _fmt_money(col_other_rate),
        "line_13_subtotal_30": _fmt_money(col_30),
        "line_14_tax_10": "",
        "line_14_tax_15": "",
        # Line 14 = "Multiply line 13 by rate of tax at top of each
        # column" — i.e. this must be the TAX for that column, not a
        # repeat of the income figure from line 13 (a confirmed bug in an
        # earlier version of this module: it wrote the income amount into
        # line 14 verbatim, so line 15 — the sum of line 14 — silently
        # disagreed with the actual tax liability whenever the rate wasn't
        # 100%). Reading tax.fdap_tax_liability directly here (rather than
        # computing col_30 * 0.30 / col_other_rate * 0.14 by hand) keeps
        # this exactly consistent with line 15 and with 1040-NR line 23a,
        # all three of which must agree.
        "line_14_tax_30": _fmt_money(fdap_tax if col_30 > 0 else 0.0),
        "line_14_tax_other_rate": _fmt_money(fdap_tax if col_other_rate > 0 else 0.0),
        "line_15_tax_total": _fmt_money(fdap_tax),
    }
