"""Form 843 — Claim for Refund / Abatement (FICA refund path).

Used when an F/J/M/Q visa holder during their exempt period had Social
Security and/or Medicare tax wrongly withheld. The employer must first
refuse to issue the refund (Form 8316 statement attached) before the
employee files Form 843.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


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

    return {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "ssn_itin": ident.primary_tin,
        "address_line1": ident.us_address_line1,
        "address_city_state_zip": f"{ident.us_city}, {ident.us_state} {ident.us_zip}",
        "period_from": f"01-01-{state.tax_year}",
        "period_to": f"12-31-{state.tax_year}",
        "line_1_amount_to_refund": total_amount,
        "line_2_period_of_claim": f"{state.tax_year}",
        "line_3_tax_type": "FICA",
        "line_4_explanation_irc_section": "IRC §3121(b)(19)",
        "line_5_employer_name": state.income.employer_name,
        "line_5_employer_ein": state.income.employer_ein,
        "line_6_dates_withheld": f"01-01-{state.tax_year} through 12-31-{state.tax_year}",
        "line_7_explanation_text": explanation,
        "signature_name": f"{ident.first_name} {ident.last_name}".strip(),
        "signature_phone": ident.daytime_phone,
        "_ss_amount": float(fica.incorrect_ss_withheld),
        "_medicare_amount": float(fica.incorrect_medicare_withheld),
    }
