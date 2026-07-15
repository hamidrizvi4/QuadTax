"""Form 1040-NR (US Nonresident Alien Income Tax Return).

Maps the finalized :class:`ReturnStateObject` to the AcroForm field names
on the vendored TY2025 Form 1040-NR (``assets/templates/2025/f1040nr.pdf``).

Field-name / line-number map below was verified against the real vendored
PDF's own widget annotations (fully-qualified AcroForm field names + each
checkbox's real ``/AP /N`` export states, walked from the raw ``/Annots``
array — NOT ``reader.get_fields()``'s ``/_States_``, which is unreliable
for multi-kid radio groups) AND its embedded XFA ``<template>`` packet's
accessibility ``<speak>`` text, which gives the IRS's own authoritative
line label for every field. Do NOT trust line-number assumptions from
older 1040-NR revisions or from field-name text alone (e.g. ``f2_10``
looks unrelated to line 23a but is real line 17) — re-verify against the
current year's own AcroForm/XFA structure if the IRS reflows the form.

Known limitation carried in from L6 (``src/agents/l6_tax_calc.py``, out of
scope for this file): ``state.tax.agi`` / ``state.tax.taxable_income`` are
computed as ECI + FDAP combined into a single bucket, whereas the real
1040-NR keeps FDAP income (Schedule NEC) completely separate from AGI/
taxable income (Schedule NEC has no deductions and never touches Line 11b/
15). Because L6 doesn't persist a "net ECI only" or "net FDAP only" figure
back to state, lines 9/11a/11b/15/16 below are internally self-consistent
with each other and with the authoritative L6 totals, but line 16 (tax)
technically isn't recomputable from line 15 (taxable income) via the
graduated brackets alone whenever FDAP income is present, since line 16
is actually computed from ECI-only income upstream. A future L6 change to
persist net_eci/net_fdap separately would let this module report a
strictly correct, ECI-only line 9/11/15 with FDAP appearing exclusively
via Schedule NEC/line 23a as the real form intends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


# Treaty-benefit categories that offset WAGES (Line 1a) specifically, as
# opposed to scholarship/fellowship income (which is reported/exempted via
# a different line entirely — Line 8 or Schedule NEC — and never nets
# against Line 1a). Shared with schedule_oi.py: Schedule OI Item L's "(e)
# Total" line is explicitly instructed to be entered on this same Line 1k
# and nowhere else, so both computations must use the identical category
# filter or the two forms would disagree on the same dollar figure.
WAGE_TREATY_CATEGORIES = frozenset(
    {
        "student_personal_services",
        "teaching_research",
        "independent_personal_services",
        "dependent_personal_services",
        "foreign_source_remittance",
    }
)


def _fmt_money(value) -> str:
    """Format money for IRS forms: whole-dollar, no commas, empty for zero/blank."""
    if value in (None, ""):
        return ""
    try:
        rounded = round(float(value))
    except (TypeError, ValueError):
        return ""
    return "" if rounded == 0 else str(rounded)


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    income = state.income
    treaty = state.treaty
    tax = state.tax

    # Line 11 (AGI), line 12 (deduction), and line 15 (taxable income) are
    # computed authoritatively by L6 and stored on state.tax. The populator
    # reads them directly rather than re-deriving — re-deriving line 15 from
    # treaty.exempt_amount_applied broke the India Art 21(2) case, where the
    # benefit is a $15k standard deduction (line 12), not a wage exemption.
    agi = float(tax.agi)
    deduction_amount = float(tax.deduction_amount)
    eci_tax = float(tax.eci_tax_liability)
    fdap_tax = float(tax.fdap_tax_liability)

    # AMT lives on ``state.amt`` (a plain dict populated by AMTCalculator —
    # see src/orchestrator/engine.py's ``state.amt = amt.to_dict_floats()``
    # and form_6251.py's own ``amt.get("amt_owed", 0.0)``), NOT on
    # ``state.tax``. TaxCalculatedState has no ``amt_owed`` field, so the
    # previous ``state.tax.amt_owed if hasattr(...) else 0.0`` check always
    # fell through to 0.0 — AMT silently never reached the 1040-NR even
    # when Form 6251 computed a real liability. Confirmed bug; fixed here.
    amt_owed = float((state.amt or {}).get("amt_owed", 0.0))

    # Withholding sources by line.
    wh = state.withholding_report or {}
    w2_withholding = float(wh.get("federal_w2", 0.0))
    withholding_1099 = float(wh.get("federal_1099", 0.0))
    withholding_1042s = float(wh.get("federal_1042s_ch3", 0.0)) + float(
        wh.get("federal_1042s_ch4", 0.0)
    )

    # Line 1k — treaty-exempt WAGES subtotal (sum across all wage-category
    # benefits; excludes India 21(2), which is a standard-deduction path,
    # not a wage exemption). Reused below for line 1a/1z so the three lines
    # can never silently disagree on the same dollar figure.
    wage_treaty_exempt = sum(
        float(b.get("exempt_amount", 0.0))
        for b in treaty.applied_benefits
        if b.get("category") in WAGE_TREATY_CATEGORIES
        and not (b.get("country_iso2") == "IN" and b.get("article_id") == "21(2)")
    )

    # Line 1a — the IRS instructions for Form 1040-NR are explicit: "Wages,
    # salaries, tips, and other compensation that you claim are exempt from
    # U.S. tax under an income tax treaty should not be reported on line
    # 1a. Instead, include these amounts on line 1k." Line 1a must
    # therefore be NET of the treaty-exempt subtotal, not gross Box-1
    # wages — the previous code reported the gross figure here (line 1a
    # equal to full W-2 wages regardless of treaty exemption), which
    # overstated taxable wage income by the full exempt amount on the face
    # of the return for every treaty-wage-exemption filer (e.g. China Art
    # 20(c)). Confirmed via IRS instructions; fixed here.
    net_wages = max(0.0, float(income.total_w2_wages) - wage_treaty_exempt)

    # Line 18 = "Add lines 16 and 17." Lines 19-21 (child tax credit /
    # Schedule 3 credits) have no state backing in this engine (no credits
    # layer implemented) so they are correctly 0/blank, which makes line 22
    # ("Subtract line 21 from line 18") collapse to line 18 unchanged.
    line_18_tax_and_amt = eci_tax + amt_owed
    line_22_after_credits = line_18_tax_and_amt

    # Line 23d = "Add lines 23a through 23c." 23b (self-employment/other
    # Schedule 2 Part II taxes) and 23c (transportation tax) have no state
    # backing anywhere in this engine — genuinely $0, not a lazy stub — so
    # the subtotal collapses to line 23a (the Schedule NEC/FDAP tax).
    line_23d_subtotal = fdap_tax

    # Line 25d = "Add lines 25a through 25c." 25c ("Other forms") has no
    # state backing, so the subtotal is just W-2 + 1099 withholding.
    line_25d_subtotal = w2_withholding + withholding_1099

    # Total tax (line 24) = regular ECI tax + AMT (line 22) + FDAP/Sch NEC
    # tax + other taxes (0) + transportation (0) (line 23d) — algebraically
    # the same total tax.total_tax_liability (eci_tax + fdap_tax) + AMT the
    # old code already produced, just now actually reconcilable line-by-line
    # against the intermediate lines above instead of appearing as an
    # unexplained lump sum with lines 18/22/23a/23d all blank.
    total_tax = float(tax.total_tax_liability) + amt_owed

    penalty = state.estimated_tax_penalty or {}

    mapping: dict[str, object] = {
        # Header — identity
        "tax_year": state.tax_year,
        "first_name_mi": f"{ident.first_name} {ident.middle_initial}".strip(),
        "last_name": ident.last_name,
        "identifying_number": ident.primary_tin,
        "us_address_line1": ident.us_address_line1,
        "us_address_line2": ident.us_address_line2,
        "us_city": ident.us_city,
        "us_state": ident.us_state,
        "us_zip": ident.us_zip,
        "foreign_country_name": ident.foreign_country,
        "foreign_province_state": ident.foreign_state_province,
        "foreign_postal_code": ident.foreign_postal_code,
        # Filing Status (real form has 5 boxes: Single / Married filing
        # separately (MFS) / Qualifying surviving spouse (QSS) / Estate /
        # Trust — verified via the vendored PDF's XFA accessibility text.
        # ReturnStateObject only models the first three (individual-filer
        # statuses valid for an NRA); Estate/Trust have no state field and
        # are intentionally left unmapped).
        "filing_status_single": True if ident.filing_status == "single" else False,
        "filing_status_mfs": True if ident.filing_status == "mfs" else False,
        "filing_status_qss": True if ident.filing_status == "qss" else False,
        # Digital Assets question (top of page 1) — from the intake extras step.
        "digital_assets_yes": state.extras.had_digital_assets,
        "digital_assets_no": not state.extras.had_digital_assets,
        # Line 1a — wages net of any treaty wage-exemption (see net_wages above).
        "line_1a_wages": _fmt_money(net_wages),
        # Line 1k — treaty-exempt wages subtotal (disclosure only; per IRS
        # instructions it is NOT subtracted again anywhere in the line 1a-1z
        # arithmetic — the exclusion already happened by omitting it from 1a).
        "line_1k_treaty_exempt_wages": _fmt_money(wage_treaty_exempt),
        # Line 1z — "Add lines 1a through 1h." Only 1a is populated in this
        # engine (1b-1h have no state backing), so 1z equals 1a exactly.
        "line_1z_total_wages_net": _fmt_money(net_wages),
        #
        # Line 8 ("Additional income from Schedule 1 (Form 1040), line 10")
        # is a catch-all for gambling winnings, debt cancellation, etc. —
        # this engine has no such income category modeled, so it is left
        # unmapped/blank. It must NOT be used for FDAP/scholarship income:
        # that is already correctly reported on Schedule NEC
        # (schedule_nec.py) and flows into 1040-NR line 23a instead: putting
        # the same dollars on both line 8 (graduated-rate ECI bucket) and
        # Schedule NEC (flat-rate FDAP bucket) would double-count it. The
        # previous code did exactly this (mapped income.fdap_taxable_total
        # onto line 8); removed as a confirmed double-count bug.
        #
        # Line 9 — "Add lines 1z, 2b, 3b, 4b, 5b, 7a, and 8." Investment
        # income (2b/3b/4b/5b/7a) and line 8 have no state backing, so a
        # literal hand-sum would just equal net_wages — but that would
        # silently diverge from the authoritative line 11a AGI whenever
        # there is non-wage ECI or FDAP income (see the module docstring's
        # note on L6's combined AGI bucket). Reusing tax.agi directly here
        # keeps "line 9 − line 10 = line 11a" exactly true (line 10
        # adjustments are always blank/unmodeled), matching this file's
        # existing policy of trusting L6's authoritative totals over
        # re-deriving them from partial state.
        "line_9_total_income": _fmt_money(agi),
        # Line 11a — AGI (authoritative figure from L6).
        "line_11_agi": _fmt_money(agi),
        # Line 11b — page 2 repeats line 11a's AGI verbatim ("Amount from
        # line 11a"). Previously unmapped entirely, leaving page 2's own
        # taxable-income derivation (11b − 14 = 15) visibly blank on the
        # printed form even though line 15 itself was filled.
        "line_11b_agi": _fmt_money(agi),
        # Line 12 — deduction (itemized OR India standard; from L6).
        "line_12_deduction": _fmt_money(deduction_amount),
        # Line 14 — "Add lines 12 through 13c." 13a (QBI)/13b (estates &
        # trusts)/13c (Schedule 1-A) have no state backing, so the subtotal
        # collapses to line 12. Previously unmapped, leaving line 15's own
        # "subtract line 14 from line 11b" derivation unexplained on the PDF.
        "line_14_deductions_subtotal": _fmt_money(deduction_amount),
        # Line 15 — taxable income (from L6: AGI − line-12 deduction).
        "line_15_taxable_income": _fmt_money(tax.taxable_income),
        # Line 16 — tax on ECI (graduated brackets, from L6).
        "line_16_tax": _fmt_money(eci_tax),
        # Line 17 — "Amount from Schedule 2 (Form 1040), line 3" = AMT +
        # excess advance premium tax credit repayment (the latter unmodeled
        # here). NOTE: this is real Line 17, NOT line 23a — line 23a is a
        # completely different amount (Schedule NEC/FDAP tax; see below).
        # The old code named this key "line_23a_amt" despite already
        # targeting the correct field (f2_10 = line 17) in the JSON remap —
        # renamed for accuracy so a future edit doesn't collide it with the
        # real line 23a now populated below.
        "line_17_sch2_amt": _fmt_money(amt_owed),
        # Line 18 — "Add lines 16 and 17." Previously unmapped.
        "line_18_tax_and_amt": _fmt_money(line_18_tax_and_amt),
        # Line 22 — "Subtract line 21 from line 18" (lines 19-21 credits
        # are unmodeled/0). Previously unmapped.
        "line_22_tax_after_credits": _fmt_money(line_22_after_credits),
        # Line 23a — "Tax on income not effectively connected... from
        # Schedule NEC (Form 1040-NR), line 15" = the FDAP flat-rate tax.
        # Previously never mapped to any field at all (a real, nonzero
        # dollar figure — already shown correctly on Schedule NEC — was
        # invisible on the 1040-NR itself for any filer with FDAP income).
        "line_23a_fdap_tax": _fmt_money(fdap_tax),
        # Line 23b — "Other taxes, including self-employment tax, from
        # Schedule 2 (Form 1040), line 21." This engine has no
        # self-employment-tax or Schedule 2 Part II computation anywhere —
        # genuinely $0 for every filer this engine supports, not a stub.
        "line_23b_other_taxes": _fmt_money(0.0),
        # Line 23d — "Add lines 23a through 23c." Previously unmapped.
        "line_23d_addl_tax_subtotal": _fmt_money(line_23d_subtotal),
        # Line 24 — total tax (ECI + AMT + FDAP/Sch NEC + other taxes).
        "line_24_total_tax": _fmt_money(total_tax),
        # Line 25a — federal withholding from W-2 box 2.
        "line_25a_w2_withholding": _fmt_money(w2_withholding),
        # Line 25b — federal withholding from 1099 forms. (Renamed from
        # "line_25c_1099_withholding" — the JSON remap already correctly
        # targeted the real line 25b field; only the Python key's own name
        # was off by a letter from the real form.)
        "line_25b_1099_withholding": _fmt_money(withholding_1099),
        # Line 25d — "Add lines 25a through 25c." Previously unmapped.
        "line_25d_subtotal": _fmt_money(line_25d_subtotal),
        # Line 25g — federal withholding from 1042-S box 7a (Ch 3 + Ch 4).
        # (Renamed from "line_25b_1042s_withholding" — same off-by-letter
        # naming issue as line 25b above; the JSON target was already
        # correct.)
        "line_25g_1042s_withholding": _fmt_money(withholding_1042s),
        # Line 26 — estimated tax payments.
        "line_26_estimated_payments": _fmt_money(wh.get("federal_estimated_payments", 0.0)),
        # Line 33 — total payments. (Renamed from "line_32_total_payments" —
        # real line 32 is "total other payments and refundable credits"
        # (ACTC/1040-C/adoption credit/Schedule 3), which this engine
        # doesn't model and is correctly left blank; this value is what the
        # real form calls line 33.)
        "line_33_total_payments": _fmt_money(tax.total_withholding_credits),
        # Line 34 — amount overpaid. (Renamed from "line_33_refund" — real
        # line 33 is total payments, above; "amount you overpaid" is line 34.)
        "line_34_overpaid": _fmt_money(max(0.0, -float(tax.refund_or_owed))),
        # Line 35a — amount of the overpayment refunded to the filer (by
        # check or direct deposit — not conditioned on direct_deposit; that
        # flag only controls whether 35b/c/d below get filled).
        "line_35a_direct_deposit_refund": _fmt_money(max(0.0, -float(tax.refund_or_owed))),
        # Line 35b/c/d — direct deposit routing/account details, only when
        # the filer actually requested direct deposit.
        "line_35b_routing_number": tax.routing_number if tax.direct_deposit else "",
        "line_35c_account_type_checking": bool(
            tax.direct_deposit and tax.account_type == "checking"
        ),
        "line_35c_account_type_savings": bool(
            tax.direct_deposit and tax.account_type == "savings"
        ),
        "line_35d_account_number": tax.account_number if tax.direct_deposit else "",
        # Line 37 — amount you owe.
        "line_37_owed": _fmt_money(max(0.0, float(tax.refund_or_owed))),
        # Line 38 — estimated tax penalty (Form 2210 worst-case estimate;
        # see src/functions/estimated_tax_penalty.py / form_2210.py's own
        # "line_17_total_penalty", which reads the same state dict).
        # Previously unmapped despite a real, already-computed state value.
        "line_38_estimated_tax_penalty": _fmt_money(penalty.get("penalty_amount", 0.0)),
        # Signature block
        "signature_occupation": ident.occupation,
        "signature_daytime_phone": ident.daytime_phone,
        "signature_email": ident.email,
    }
    return mapping
