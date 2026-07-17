"""Form IT-203 — NY Nonresident / Part-Year Resident Income Tax Return.

Maps the finalized :class:`ReturnStateObject` to the real AcroForm field
names on the vendored NY DTF IT-203 (2025) PDF (verified via a position-
correlated field/text dump of the actual template, not assumed from a
generic 1040-style layout).

Column semantics on the IT-203 income-reconciliation lines (1-31): the
"Federal amount" column is the figure that appears on the attached
federal return; the "New York State amount" column is the NY-source
portion for a nonresident/part-year filer (NY instructs nonresidents to
fill in the NY column for lines that show NY-source income — see IT-203-I).
This engine doesn't track income line-by-line (interest, dividends, etc.
— it only sees wages and FDAP), so only the lines it has real data for
are populated:

    Line 1  (Wages): federal = W-2 wages NET of any wage-category treaty
             exemption — this MUST equal Form 1040-NR line 1a exactly,
             because IRS instructions require treaty-exempt wages to be
             excluded from line 1a (reported on line 1k instead), not
             included and then backed out later. Using gross wages here
             (as a prior version of this module did) makes IT-203 line 1
             visibly disagree with the attached federal return's line 1a
             for every treaty-wage-exemption filer — a real, auditable
             discrepancy, not just a cosmetic one. NY column = NY-source
             wages (NY doesn't honor the treaty, so this stays gross).
    Line 16 (Other income): federal = FDAP/1042-S total NET of any
             scholarship-category treaty exemption (same reasoning as
             line 1 — the exemption is already excluded, not a later
             "adjustment"); NY = NY-source 1042-S gross (NY doesn't honor
             treaties, so NY column stays gross; only populated when the
             filer has any 1042-S income at all, even if fully exempted).
    Line 17 (subtotal, "Add lines 1-11, 13-16"): federal = net line 1 +
             net line 16; NY = NY line 1 + NY line 16.
    Line 18 (Total federal adjustments to income — i.e. federal Schedule 1
             Part II items like IRA/HSA/student-loan-interest deductions):
             genuinely $0/blank for every filer this engine supports (no
             such adjustments are modeled) and, critically, is NOT where a
             treaty exemption belongs — a treaty wage/FDAP exemption is
             excluded directly from lines 1/16 above (see above), never
             subtracted again here. A prior version of this module put
             treaty_addback on this line, which was wrong on two counts:
             wrong category (treaty exemptions aren't Schedule 1
             adjustments) and double-application in spirit (line 1 was
             gross AND line 18 subtracted the exemption again, coincidentally
             netting to the same total federal AGI in the common case but
             showing the exemption on the wrong line of the printed form).
    Line 19 (Federal AGI) = line 17 - line 18 (=0) = net line 1 + net line
             16, both columns. This is *not* re-derived from
             ``state.tax.agi`` (the 1040-NR's own authoritative AGI figure)
             because that would break this form's own "17 - 18 = 19"
             arithmetic whenever L6's AGI diverges from the visible sum
             (e.g. 1042-S income routed to the ECI bucket) — a known,
             pre-existing L6/L9 modeling gap (see form_1040nr.py's module
             docstring) that's out of scope for this PDF-mapping pass.
             The two numbers coincide in the common case (no routed ECI).
    Lines 20-21 (other NY additions): no data, left blank.
    Line 22 (Other additions, Form IT-225 line 9): federal = treaty_addback
             (the required NY addback of ALL federal treaty exemptions,
             wage and FDAP alike, since NY honors none of them); NY = 0
             (NY-source wages/FDAP were computed pre-treaty already —
             nothing to add back on the NY side).
    Line 23 (19+20+21+22): federal = ny_agi; NY = ny_source_income. (Uses
             the authoritative NY-calculator totals directly rather than
             hand-summing 19+22, since lines 2-15/20-21 aren't tracked and
             a hand-sum would only equal ny_agi when there's no routed ECI
             — same caveat as line 19 above.)
    Lines 24-30 (NY subtractions): no data, left blank (all $0 lines).
    Line 31 (NY AGI), Line 32, Line 45's two dollar sub-fields: filled
             directly from ``state.ny.ny_agi`` / ``state.ny.ny_source_income``
             (the authoritative, already-computed figures) rather than
             re-derived from the chain above, though they match by
             construction.

Lines 38/40/42/44 (state tax after nonrefundable credits) are all set to
the same ``ny_tax_resident_basis`` value since this engine computes no NY
credits (household credit, dependent care credit, EITC) — the "subtract
credit" lines are pass-throughs when the credit amount is $0.

NYC tax (line 51) and Yonkers tax (line 54) only ever come from the
resident/part-year-resident code paths in ``ny_tax_math.NYTaxCalculator``
(nonresident-Yonkers-earnings tax is computed by that module but never
wired with real data by ``l9_ny.py``, so it's always $0 today — a
pre-existing gap, not something this PDF-mapping pass fixes).

Fields with no backing intake data (foreign financial account disclosure,
Yonkers-living-quarters months, part-year NYS move date/residency detail,
NY county of residence, dependents chart, third-party designee, paid
preparer section, MCTMT net-earnings base and tax (lines 52b-52f), spouse's
occupation/date-of-birth, "other penalties and interest" (line 72),
foreign-account-for-refund/EFW checkbox) are deliberately left unmapped
rather than guessed. Signature/date fields (taxpayer's own signing date)
are also deliberately left blank even though a "today's date" value could
be computed — the signature date must reflect when the filer actually
signs, which is unknowable at PDF-assembly time, and
``FormPopulator._inject_pdf_data`` flattens (locks) every field on write,
so a wrong pre-filled date could never be corrected by the filer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.assembly.forms.form_1040nr import WAGE_TREATY_CATEGORIES

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


# Treaty-benefit categories that offset FDAP/scholarship income specifically
# (mirrors src/agents/l6_tax_calc.py's private ``_FDAP_TREATY_CATEGORIES``,
# which isn't exported for reuse — kept in sync here by hand). Used to net
# IT-203 line 16 down to the same post-treaty figure L6 uses when building
# ``state.tax.agi``, the same way ``WAGE_TREATY_CATEGORIES`` (imported
# above) nets line 1.
_FDAP_TREATY_CATEGORIES = frozenset({"scholarship_fellowship"})


def _fmt_money(value) -> str:
    if value in (None, ""):
        return ""
    try:
        rounded = round(float(value))
    except (TypeError, ValueError):
        return ""
    return "" if rounded == 0 else str(rounded)


def _fmt_money_always(value) -> str:
    """Like _fmt_money but never collapses $0 to blank (for "do not leave
    blank" lines, e.g. IT-203 line 56 sales/use tax)."""
    try:
        rounded = round(float(value or 0))
    except (TypeError, ValueError):
        rounded = 0
    return str(rounded)


def _fmt_mmddyyyy(iso_date) -> str:
    if not iso_date:
        return ""
    try:
        y, m, d = str(iso_date).split("-")
        return f"{m}{d}{y}"
    except ValueError:
        return ""


def _split_phone(phone) -> tuple[str, str]:
    """Split a free-text daytime phone number into (area code, remainder).

    IT-203's signature block (unlike the federal 1040-NR's single phone
    field) has two separate boxes: a 3-digit area-code box and a
    remaining-digits box. ``Identity.daytime_phone`` is free text with no
    guaranteed format, so this only splits when it unambiguously parses as
    a 10-digit US number; anything else (missing, international, malformed)
    is left as two blanks rather than guessing where the area code ends.
    """
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10:
        return digits[:3], digits[3:]
    return "", ""


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    ny = state.ny
    extras = state.extras
    tax = state.tax
    treaty = state.treaty
    sch_a = state.sch_a or {}

    treaty_addback = float(ny.ny_treaty_addback)
    fdap_total = float(state.income.fdap_taxable_total)
    itemized = float(sch_a.get("total", 0.0)) > 0

    # Net wages/FDAP down by the same treaty-category filters form_1040nr.py
    # and l6_tax_calc.py use, so IT-203 line 1/16 agree, dollar-for-dollar,
    # with 1040-NR lines 1a/(AGI build) instead of showing the pre-treaty
    # gross figure the printed federal return never actually reports. See
    # module docstring for why this matters (a real cross-form discrepancy,
    # not cosmetic).
    wage_treaty_exempt = sum(
        float(b.get("exempt_amount", 0.0))
        for b in treaty.applied_benefits
        if b.get("category") in WAGE_TREATY_CATEGORIES
        and not (b.get("country_iso2") == "IN" and b.get("article_id") == "21(2)")
    )
    scholarship_treaty_exempt = sum(
        float(b.get("exempt_amount", 0.0))
        for b in treaty.applied_benefits
        if b.get("category") in _FDAP_TREATY_CATEGORIES
    )
    net_wages = max(0.0, float(state.income.total_w2_wages) - wage_treaty_exempt)
    net_fdap = max(0.0, fdap_total - scholarship_treaty_exempt)

    refund_due = max(0.0, -float(ny.ny_refund_or_owed))
    amount_owed = max(0.0, float(ny.ny_refund_or_owed))

    # NB: the MFS export state contains a mis-encoded apostrophe baked into
    # the real vendored PDF's AcroForm (the byte sequence for "'s" was
    # mangled into a single CJK codepoint, U+6060, during the vendor's PDF
    # authoring — verified byte-for-byte against the real widget's /AP/N
    # export state, which reads literally "...enter spouse恠 social
    # security number above)" with NO separate "s" after the mangled
    # character). This must match byte-for-byte or pypdf's checkbox
    # pass-through in _format_for_acro won't match any of the field's real
    # export states and the MFS box will silently render unchecked. Use the
    # escape (not a literal character) so this doesn't silently rot on
    # re-save/re-encode.
    filing_status_state = {
        "single": "/1 Single",
        "mfs": "/3 Married Filing Seperate Return (enter spouse恠 social security number above)",
        "qss": "/Qualifying widow(er) with dependent child",
    }.get(ident.filing_status, "/1 Single")

    field_map = {
        # Header — identity
        "your_first_name": ident.first_name,
        "your_last_name": ident.last_name,
        "your_dob": _fmt_mmddyyyy(ident.date_of_birth),
        "your_ssn": ident.primary_tin,
        "mailing_address": ident.us_address_line1,
        "apartment_number_1": ident.us_address_line2,
        "city_1": ident.us_city,
        "state_1": ident.us_state,
        "zip_1": ident.us_zip,
        # Permanent home address section duplicates the mailing address —
        # this engine's population's US address (dorm/apartment) generally
        # *is* their home while filing; see module docstring.
        "permanent_home_address": ident.us_address_line1,
        "apartment_number_2": ident.us_address_line2,
        "city_2": ident.us_city,
        "state_2": ident.us_state,
        "zip_2": ident.us_zip,
        "filing_status": filing_status_state,
        # Item B — itemized on federal return? (mirrors the IT-203-D
        # attach condition: itemized only when federal Sch A total > 0)
        "item_b_itemized": "/yes" if itemized else "/no",
        # Item C — can be claimed as a dependent on another's federal return
        "item_c_dependent": "/yes" if extras.can_be_claimed_as_dependent else "/no",
        # Item H — maintained living quarters in NYS during 2025. NB: the
        # real AcroForm field is internally named "In NYC" (a vendor
        # misnomer baked into the PDF) but the printed label right next to
        # it reads "Did you or your spouse maintain living quarters in NYS
        # in 2025?" — verified via position-correlated text extraction, not
        # the field's own (misleading) name.
        "item_h_living_quarters": "/yes" if ny.abode_months_in_year > 0 else "/no",
        "signature_occupation": ident.occupation,
        # Signature-block contact info (page 4). IT-203 splits the phone
        # number into a separate area-code box, unlike the federal 1040-NR's
        # single field — see _split_phone.
        "signature_phone_area_code": _split_phone(ident.daytime_phone)[0],
        "signature_phone_number": _split_phone(ident.daytime_phone)[1],
        "signature_email": ident.email,
        # Income reconciliation (Federal / NY columns) — see docstring for
        # why line 1/16/17/18/19 are net-of-treaty rather than the prior
        # gross-wages-then-subtract-on-line-18 approach.
        "line_1_federal": _fmt_money(net_wages),
        "line_1_ny": _fmt_money(ny.ny_source_wages),
        "line_17_federal": _fmt_money(net_wages + net_fdap),
        "line_17_ny": _fmt_money(ny.ny_source_wages + ny.ny_source_1042s_gross),
        # Line 18 ("Total federal adjustments to income") is genuinely $0 —
        # no Schedule 1 Part II adjustments are modeled by this engine, and
        # (per the docstring) the treaty exemption does NOT belong here; it
        # was already excluded directly from lines 1/16 above. Left out of
        # the map entirely (renders blank), matching this file's existing
        # "$0 means omit the key" convention.
        "line_19_federal": _fmt_money(net_wages + net_fdap),
        "line_19_ny": _fmt_money(ny.ny_source_wages + ny.ny_source_1042s_gross),
        "line_22_federal": _fmt_money(treaty_addback),
        "line_23_federal": _fmt_money(ny.ny_agi),
        "line_23_ny": _fmt_money(ny.ny_source_income),
        "line_31_federal": _fmt_money(ny.ny_agi),
        "line_31_ny": _fmt_money(ny.ny_source_income),
        "line_32_federal": _fmt_money(ny.ny_agi),
        # Line 33 — standard or itemized deduction
        "deduction_type": "/Itemized" if itemized else "/Standard",
        "line_33_dollars": _fmt_money(
            sch_a.get("total", 0.0) if itemized else ny.ny_standard_deduction
        ),
        "line_34_dollars": _fmt_money(
            max(0.0, ny.ny_agi - (sch_a.get("total", 0.0) if itemized else ny.ny_standard_deduction))
        ),
        # Line 35 — dependent exemptions ($1,000 each): no dependents tracked.
        "line_36_dollars": _fmt_money(ny.ny_taxable_income),
        "line_37_dollars": _fmt_money(ny.ny_taxable_income),
        "line_38_dollars": _fmt_money(ny.ny_tax_resident_basis),
        "line_40_dollars": _fmt_money(ny.ny_tax_resident_basis),
        "line_42_dollars": _fmt_money(ny.ny_tax_resident_basis),
        "line_44_dollars": _fmt_money(ny.ny_tax_resident_basis),
        "line_45_percent": f"{float(ny.ny_income_percentage):.4f}",
        "line_45_nys_dollars": _fmt_money(ny.ny_source_income),
        "line_45_federal_dollars": _fmt_money(ny.ny_agi),
        "line_46_dollars": _fmt_money(ny.ny_tax_apportioned),
        "line_48_dollars": _fmt_money(ny.ny_tax_apportioned),
        "line_50_dollars": _fmt_money(ny.ny_tax_apportioned),
        "line_51_dollars": _fmt_money(ny.nyc_tax),
        "line_52a_dollars": _fmt_money(ny.nyc_tax),
        "line_54_dollars": _fmt_money(ny.yonkers_tax),
        "line_55_dollars": _fmt_money(ny.nyc_tax + ny.yonkers_tax),
        # Line 56 — sales/use tax; form explicitly says "Do not leave blank."
        "line_56_dollars": _fmt_money_always(0),
        "line_58_dollars": _fmt_money(ny.total_ny_state_local),
        "line_59_dollars": _fmt_money(ny.total_ny_state_local),
        "line_62_dollars": _fmt_money(ny.ny_withholding),
        "line_63_dollars": _fmt_money(ny.nyc_withholding),
        "line_66_dollars": _fmt_money(ny.ny_withholding + ny.nyc_withholding),
        "line_67_dollars": _fmt_money(refund_due),
        "line_68_dollars": _fmt_money(refund_due),
        # Line 68a (amount of line 68 deposited into a NYS 529 account) is
        # unmodeled/always $0 — no 529-deposit intake exists — so line 68b
        # ("Total refund after NYS 529 account deposit", i.e. 68 - 68a)
        # algebraically collapses to line 68 unchanged. This is a real,
        # derived value (not a fabrication): previously omitted entirely,
        # leaving the final refund total blank on the printed form even
        # though line 68 right above it was filled.
        "line_68b_dollars": _fmt_money(refund_due),
        "line_70_dollars": _fmt_money(amount_owed),
        "_residency_reason": ny.residency_reason,
        "_note": (
            "Not populated (no supporting intake data): NY county of "
            "residence; foreign financial account disclosure (Item D1); "
            "Yonkers living-quarters months/checkbox (Item D2); NYC months "
            "lived (Item E); special condition codes (Item F); part-year "
            "NYS move date and residency detail (Items G/1-3); dependents "
            "chart; third-party designee; paid preparer section; MCTMT net-"
            "earnings base and tax (lines 52b-52f, Zones 1/2 — no MCTMT "
            "computation exists anywhere in this engine); 'other penalties "
            "and interest' (line 72); spouse's occupation and date of "
            "birth; foreign-account-for-refund/EFW checkbox (page 4 — "
            "correctly left unchecked, since routing/account numbers "
            "captured by this engine are assumed domestic US accounts). "
            "Sales/use tax (line 56) defaulted to $0 — verify with filer. "
            "Yonkers nonresident-earnings tax (line 53) is always $0 in "
            "this engine's current wiring even when applicable — see "
            "src/functions/ny_tax_math.py's yonkers_nonresident_earnings "
            "parameter, which l9_ny.py never populates. NYC tax (line 51) "
            "is computed via the resident-basis NYC brackets as a "
            "simplification of the real Form IT-360.1 part-year "
            "computation the printed line actually calls for — a "
            "pre-existing ny_tax_math.py approximation, not something "
            "this PDF-mapping pass changes."
        ),
    }

    # Refund method — mark a choice whenever a refund is actually due; leave
    # both radio states off when there's no refund (a balance-due filer
    # picks a payment method via lines 70/73/74 instead, which this engine
    # also doesn't model — see _note).
    if refund_due > 0:
        if tax.direct_deposit:
            field_map["refund_method"] = "/direct deposit"
            field_map["account_type"] = (
                "/Personal savings" if tax.account_type == "savings" else "/Personal checking"
            )
            field_map["routing_number"] = tax.routing_number
            field_map["account_number"] = tax.account_number
        else:
            # The real export state for "paper check" is confusingly named
            # "/debit card" in the vendored PDF's own AcroForm (verified via
            # the raw widget /AP/N dump — there is no "debit card" text
            # printed anywhere on the form itself; this is a vendor
            # artifact, not a typo introduced here). Explicitly marking it
            # — rather than leaving both refund-method boxes blank, as a
            # prior version of this module did — avoids an ambiguous
            # printed return whenever a refund is due but no bank details
            # were captured.
            field_map["refund_method"] = "/debit card"

    # Spouse fields — IT-203 (unlike the federal 1040-NR) has real spouse
    # identification lines; wire them for MFS/QSS filers who provided them.
    if ident.filing_status in ("mfs", "qss") and ident.spouse_ssn_or_itin:
        field_map["spouse_first_name"] = ident.spouse_first_name
        field_map["spouse_last_name"] = ident.spouse_last_name
        field_map["spouse_ssn"] = ident.spouse_ssn_or_itin

    if fdap_total > 0:
        field_map["line_16_identify"] = "Scholarship/fellowship income (Form 1042-S)"
        field_map["line_16_federal"] = _fmt_money(net_fdap)
        field_map["line_16_ny"] = _fmt_money(ny.ny_source_1042s_gross)

    return field_map
