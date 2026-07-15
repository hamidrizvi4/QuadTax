"""Form 843 — Claim for Refund / Abatement (FICA refund path).

Used when an F/J/M/Q visa holder during their exempt period had Social
Security and/or Medicare tax wrongly withheld. The employer must first
refuse to issue the refund (Form 8316 statement attached) before the
employee files Form 843.

Real AcroForm field layout (dumped from assets/templates/2025/f843.pdf via
raw widget annotations — /AP/N export states, not reader.get_fields()'s
/_States_ summary — and cross-referenced against the printed line text via
position-sorted extract_text). Notes on things that are easy to get wrong:

    Page 1:
        c1_1[0..16]   Line "Check the box that indicates your reason for
                       filing Form 843" (items a-q). Each index is an
                       INDEPENDENT /Btn field with its own two-state export
                       set (e.g. c1_1[4]'s states are ['/5','/Off']), not a
                       shared radio group — a bare Python bool resolves
                       correctly via FormPopulator's /_States_ fallback as
                       long as the correct kid index is targeted. Item e
                       (c1_1[4], "Refund to employee of social security,
                       Medicare, or RRTA tax withheld in error, but only if
                       your employer will not adjust the overcollection") is
                       the correct box for an NRA FICA-exemption refund —
                       NOT item c (c1_1[2]), which is for excess (over the
                       annual wage-base cap) withholding, a different fact
                       pattern.
        f1_1[0]        The free-text "specify" line for item q ("Other
                       (specify)") ONLY — sits directly beside c1_1[16].
                       NOT a general "type of tax" field. Writing "FICA"
                       here (as the pre-audit version did) both mismarks the
                       claim as an "Other" reason and leaves an orphaned
                       answer unconnected to any checked box.
        f1_2/f1_3      Name of person requesting refund / that person's SSN.
        f1_4/f1_5      Spouse name / spouse SSN (joint-return claims only —
                       out of scope, this engine never files MFJ for NRAs).
        f1_6/f1_7      Street address / Apt., room, or suite no.
        f1_8/f1_9/f1_10  City, town, or post office / State / ZIP code —
                       THREE SEPARATE boxes, not one combined string field.
        f1_11          Employer ID number (EIN) — despite sitting on the
                       same row as the address, this is the FILER'S claim
                       identification block, not a labeled "employer name"
                       line; there is no separate employer-name text field
                       anywhere on this form.
        f1_12/f1_13/f1_14  Foreign country name / foreign province-state-
                       county / foreign postal code — additional boxes used
                       only when the address above is itself foreign.
        f1_15          "Name and address shown on return if different from
                       above" — for a taxpayer whose name/address on the
                       return this claim relates to differs from the name/
                       address given above. This engine's 1040-NR always
                       uses the same identity, so there is never a
                       "different from above" name — correctly always
                       blank. (The pre-audit version wrote the EMPLOYER's
                       name into this field, which is wrong on two counts:
                       wrong concept, and not even the filer's own name.)
        f1_16          Daytime telephone number.
        f1_17/f1_18    Line 1 — tax period beginning / ending date.
        f1_19          Line 2 — amount to be refunded or abated.
        f1_20..f1_31   Line 3 — date(s) of payment(s) being claimed (12
                       slots, two rows of 6: a-f, g-l). No intake/state
                       field captures per-paycheck FICA withholding dates
                       (only the annual W-2 totals), so these are left
                       blank — see NOT-FIXABLE note below.
        c1_2[0]..c1_8[0]  Line 4 — type of tax: a Employment, b Estate,
                       c Gift, d Excise, e Income, f Fee, g Civil penalty.
                       FICA/SS/Medicare is an employment tax -> box a
                       (c1_2[0]).
    Page 2:
        c2_1[0]..c2_14[0]  Line 5 — type of return the tax relates to:
                       a 706, b 709, c 940, d 941, e 943, f 944, g 945,
                       h 990-PF, i 1040, j 1120, k 4720, l CT-2,
                       m Branded Prescription Drug (BPD) Fee, n Other
                       (specify, paired text field f2_1[0]). FICA/SS/
                       Medicare is reported by the employer on Form 941 ->
                       box d (c2_4[0]).
        f2_2[0]        Line 6 — Internal Revenue Code section for a penalty
                       claim. Not strictly a penalty claim, but IRS
                       instructions accept citing the substantive Code
                       section here for an "in error" withholding claim.
        c2_15[0..3]    Line 7 — reason for penalty/interest abatement
                       (a-d). Only applicable to penalty/interest claims
                       (line 1 items g-n), not to a FICA refund (line 1
                       item e) — correctly left entirely unchecked.
        f2_3[0]        Line 8 — explanation (nested under ExplainWhy[0]).
        f2_4/f2_5      Identity Protection PIN boxes (filer/spouse) — no
                       intake field collects an IP PIN; correctly blank.
        f2_6..f2_11, c2_16[0]  Paid Preparer Use Only block — this engine
                       does not act as a paid preparer; correctly blank.

NOT FIXABLE with current state data (documented per audit instructions,
left blank rather than fabricated):
    * f1_20..f1_31 (Line 3, per-payment dates) — only annual W-2 box 4/6
      totals are captured (FicaState.incorrect_ss_withheld /
      incorrect_medicare_withheld), never individual paycheck dates.
    * f1_15 (name/address if different from return) — no scenario in this
      engine produces a return-name mismatch; there is no field to source
      this from even if it did.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def _fmt_money(value) -> str:
    """Format money for IRS forms: whole-dollar, no commas, empty for zero/blank.

    Matches the convention used by every other form populator (see
    form_1040nr.py, schedule_a.py, etc.) — without this, a raw Python float
    like ``2295.0`` gets written to the PDF as the literal string "2295.0"
    instead of "2295".
    """
    if value in (None, ""):
        return ""
    try:
        rounded = round(float(value))
    except (TypeError, ValueError):
        return ""
    return "" if rounded == 0 else str(rounded)


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    fica = state.fica

    total_amount = float(fica.incorrect_ss_withheld) + float(fica.incorrect_medicare_withheld)

    # The evidence clause must reflect what the filer actually confirmed —
    # Form 8316 is the FILER's own self-certification (not an employer
    # document), and asserting the employer was asked when that hasn't been
    # confirmed would misstate a fact on a document filed under penalty of
    # perjury.
    if fica.has_form_8316:
        evidence_clause = (
            "The employer has confirmed in writing that it will not issue a "
            "refund; a copy of that statement is attached."
        )
    elif fica.employer_attempted_refund:
        evidence_clause = (
            "The filer requested a refund from the employer and did not "
            "receive one. Form 8316 (the filer's own certification, "
            "attached) documents this per Treas. Reg. §31.3121(b)(19)-1(a), "
            "since no written employer statement is available."
        )
    else:
        evidence_clause = (
            "Form 8316 (the filer's own certification, attached) is "
            "provided per Treas. Reg. §31.3121(b)(19)-1(a). The filer should "
            "request a refund from the employer before mailing this claim, "
            "if not already done."
        )

    explanation = (
        "Refund of Social Security and Medicare taxes withheld in error from a "
        "nonresident alien on a {visa} visa during the exempt period under IRC "
        "§3121(b)(19) and Treas. Reg. §31.3121(b)(19)-1. {evidence} Copies of "
        "W-2(s) showing the withholding and Form I-94 evidencing visa status "
        "are attached."
    ).format(visa=state.residency.exempt_visa_type or "F-1", evidence=evidence_clause)

    # Legal name for a document filed under penalty of perjury should
    # include middle initial / suffix when on file, not just first + last.
    name_parts = [ident.first_name, ident.middle_initial, ident.last_name, ident.suffix]
    full_name = " ".join(p for p in name_parts if p)

    # Address block — Form 843's "City, town, or post office" / "State" /
    # "ZIP code" are three SEPARATE boxes (f1_8/f1_9/f1_10), not one
    # combined string. When the filer has already left the US and only a
    # foreign address is on file, use that as the primary mailing address
    # (the form accepts a foreign address on the same line per its own
    # instructions) and populate the dedicated foreign country/province/
    # postal-code boxes; the domestic State/ZIP boxes stay blank in that
    # case since they don't apply to a foreign address.
    has_us_address = bool(ident.us_address_line1)
    if has_us_address:
        address_line1 = ident.us_address_line1
        address_apt = ident.us_address_line2
        address_city = ident.us_city
        address_state = ident.us_state
        address_zip = ident.us_zip
        foreign_country_name = ""
        foreign_province_county = ""
        foreign_postal_code = ""
    else:
        address_line1 = ident.foreign_address_line1
        address_apt = ident.foreign_address_line2
        address_city = ident.foreign_city
        address_state = ""
        address_zip = ""
        foreign_country_name = ident.foreign_country
        foreign_province_county = ident.foreign_state_province
        foreign_postal_code = ident.foreign_postal_code

    return {
        "name": full_name,
        "ssn_itin": ident.primary_tin,
        "address_line1": address_line1,
        "address_apt_suite": address_apt,
        "address_city": address_city,
        "address_state": address_state,
        "address_zip": address_zip,
        "foreign_country_name": foreign_country_name,
        "foreign_province_county": foreign_province_county,
        "foreign_postal_code": foreign_postal_code,
        "period_from": f"01-01-{state.tax_year}",
        "period_to": f"12-31-{state.tax_year}",
        "line_1_amount_to_refund": _fmt_money(total_amount),
        # Descriptive metadata only (not written to a PDF field — see the
        # module docstring: f1_1[0] is the "Other (specify)" line for item
        # q, unrelated to this claim, which instead checks item e below).
        "line_3_tax_type": "FICA",
        "line_4_explanation_irc_section": "IRC §3121(b)(19)",
        # Line 1 reason: item e — SS/Medicare/RRTA withheld in error,
        # employer will not adjust the overcollection.
        "line_1_reason_withheld_in_error": True,
        # Line 4 type of tax: item a — Employment.
        "line_4_type_of_tax_employment": True,
        # Line 5 return type: item d — Form 941 (the employer's quarterly
        # return on which the erroneous FICA withholding was reported).
        "line_5_return_type_941": True,
        "line_5_employer_ein": state.income.employer_ein,
        # Descriptive metadata only (not written to a PDF field). Line 3's
        # 12 boxes (f1_20..f1_31) each want a single MM/DD/YYYY per-payment
        # date; only annual W-2 box 4/6 totals are captured anywhere in
        # state, never individual paycheck dates, so there is no correct
        # per-slot value to fabricate. Cramming a "Jan-Dec" range into the
        # first slot (the pre-audit behavior) misrepresents a single-date
        # field and leaves items b-l inexplicably blank, so it was removed
        # rather than kept.
        "line_6_dates_withheld": f"01-01-{state.tax_year} through 12-31-{state.tax_year}",
        "line_7_explanation_text": explanation,
        "signature_name": full_name,
        "signature_phone": ident.daytime_phone,
        "_ss_amount": float(fica.incorrect_ss_withheld),
        "_medicare_amount": float(fica.incorrect_medicare_withheld),
    }
