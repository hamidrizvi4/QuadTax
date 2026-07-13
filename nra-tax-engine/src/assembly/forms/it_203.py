"""Form IT-203 — NY Nonresident / Part-Year Resident Income Tax Return.

Maps the finalized :class:`ReturnStateObject` to the real AcroForm field
names on the vendored NY DTF IT-203 (2025) PDF (verified via a position-
correlated field/text dump of the actual template, not assumed from a
generic 1040-style layout).

Column semantics on the IT-203 income-reconciliation lines (1-31): the
"Federal amount" column is the true all-source figure; the "New York
State amount" column is the NY-source portion for a nonresident/part-year
filer. This engine doesn't track income line-by-line (interest, dividends,
etc. — it only sees wages and FDAP), so only the lines it has real data
for are populated:

    Line 1  (Wages): federal = gross W-2 wages; NY = NY-source wages.
    Line 16 (Other income): federal = FDAP/1042-S total; NY = NY-source
             1042-S gross (only populated when nonzero).
    Line 17 (subtotal): federal = 1+16; NY = 1+16 (NY columns).
    Line 18 (Federal adjustments — treaty exemption): federal =
             treaty_addback (NY does not honor federal treaties, so this
             is subtracted federally then added back on line 22 for NY);
             NY column = 0, since NY-source wages/FDAP were computed
             pre-treaty already (nothing to subtract-then-add-back there).
    Line 19 (Federal AGI) = line 17 - line 18, both columns.
    Lines 20-21 (other NY additions): no data, left blank.
    Line 22 (Other additions, Form IT-225 line 9): federal = treaty_addback
             (the required NY treaty-income addback); NY = 0 (see line 18).
    Line 23 (19+20+21+22): federal = ny_agi; NY = ny_source_income.
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
preparer section) are deliberately left unmapped rather than guessed.
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


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    ny = state.ny
    extras = state.extras
    tax = state.tax
    sch_a = state.sch_a or {}

    treaty_addback = float(ny.ny_treaty_addback)
    fdap_total = float(state.income.fdap_taxable_total)
    itemized = float(sch_a.get("total", 0.0)) > 0

    # NB: the MFS export state contains a mis-encoded apostrophe baked into
    # the real vendored PDF's AcroForm ("spouse恠s"); this must match
    # byte-for-byte or pypdf's checkbox pass-through in _format_for_acro
    # won't match any of the field's real export states. Use the escape
    # (not a literal character) so this doesn't silently rot on re-save.
    filing_status_state = {
        "single": "/1 Single",
        "mfs": "/3 Married Filing Seperate Return (enter spouse恠s social security number above)",
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
        # Item H — maintained living quarters in NYS during 2025
        "item_h_living_quarters": "/yes" if ny.abode_months_in_year > 0 else "/no",
        "signature_occupation": ident.occupation,
        # Income reconciliation (Federal / NY columns) — see docstring.
        "line_1_federal": _fmt_money(state.income.total_w2_wages),
        "line_1_ny": _fmt_money(ny.ny_source_wages),
        "line_17_federal": _fmt_money(state.income.total_w2_wages + fdap_total),
        "line_17_ny": _fmt_money(ny.ny_source_wages + ny.ny_source_1042s_gross),
        "line_19_federal": _fmt_money(ny.ny_agi - treaty_addback),
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
        "line_67_dollars": _fmt_money(max(0.0, -ny.ny_refund_or_owed)),
        "line_68_dollars": _fmt_money(max(0.0, -ny.ny_refund_or_owed)),
        "line_70_dollars": _fmt_money(max(0.0, ny.ny_refund_or_owed)),
        "_residency_reason": ny.residency_reason,
        "_note": (
            "Not populated (no supporting intake data): NY county of "
            "residence; foreign financial account disclosure (Item D1); "
            "Yonkers living-quarters months (Item D2); NYC months lived "
            "(Item E); special condition codes (Item F); part-year NYS "
            "move date and residency detail (Items G/1-3); dependents "
            "chart; third-party designee; paid preparer section. Sales/"
            "use tax (line 56) defaulted to $0 — verify with filer. "
            "Yonkers nonresident-earnings tax (line 53) is always $0 in "
            "this engine's current wiring even when applicable — see "
            "src/functions/ny_tax_math.py's yonkers_nonresident_earnings "
            "parameter, which l9_ny.py never populates."
        ),
    }

    # Refund method — only mark a choice when direct deposit was actually
    # requested; otherwise leave both radio states off (implies paper
    # check, the safe default absent bank details).
    if tax.direct_deposit and max(0.0, -ny.ny_refund_or_owed) > 0:
        field_map["refund_method"] = "/direct deposit"
        field_map["account_type"] = (
            "/Personal savings" if tax.account_type == "savings" else "/Personal checking"
        )
        field_map["routing_number"] = tax.routing_number
        field_map["account_number"] = tax.account_number

    # Spouse fields — IT-203 (unlike the federal 1040-NR) has real spouse
    # identification lines; wire them for MFS/QSS filers who provided them.
    if ident.filing_status in ("mfs", "qss") and ident.spouse_ssn_or_itin:
        field_map["spouse_first_name"] = ident.spouse_first_name
        field_map["spouse_last_name"] = ident.spouse_last_name
        field_map["spouse_ssn"] = ident.spouse_ssn_or_itin

    if fdap_total > 0:
        field_map["line_16_identify"] = "Scholarship/fellowship income (Form 1042-S)"
        field_map["line_16_federal"] = _fmt_money(fdap_total)
        field_map["line_16_ny"] = _fmt_money(ny.ny_source_1042s_gross)

    if treaty_addback > 0:
        field_map["line_18_identify"] = "Income tax treaty exemption (Form 8833)"
        field_map["line_18_federal"] = _fmt_money(treaty_addback)

    return field_map
