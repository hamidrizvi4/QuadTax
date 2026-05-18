"""Form W-7 — Application for IRS Individual Taxpayer Identification Number.

Attached to Form 1040-NR when the filer has no SSN and no existing ITIN
(or the ITIN has expired due to 3-year non-use).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity

    reason_code = "f"  # NRA student/professor — default
    if any(b.get("requires_form_8833") for b in state.treaty.applied_benefits):
        reason_code = "a"  # NRA required to obtain ITIN to claim treaty benefit
    elif not (state.residency.exempt_visa_type or "").startswith(("F", "J", "M", "Q")):
        reason_code = "b"  # NRA filing a US tax return (generic)

    return {
        "reason_code": reason_code,
        "name_line1": f"{ident.first_name} {ident.last_name}".strip(),
        "name_at_birth": f"{ident.first_name} {ident.last_name}".strip(),
        "mailing_address_line1": ident.us_address_line1,
        "mailing_city_state_zip": f"{ident.us_city}, {ident.us_state} {ident.us_zip}".strip(", "),
        "foreign_address_line1": ident.foreign_address_line1,
        "foreign_address_country": ident.foreign_country,
        "birth_date": ident.date_of_birth or "",
        "country_of_birth": ident.foreign_country,
        "country_of_citizenship": ident.country_of_citizenship,
        "passport_number": ident.passport_number,
        "passport_country": ident.passport_country,
        "applicant_signature_name": f"{ident.first_name} {ident.last_name}".strip(),
        "applicant_phone": ident.daytime_phone,
        "treaty_country_when_reason_a": (
            ident.country_of_tax_residence if reason_code == "a" else ""
        ),
        "treaty_article_when_reason_a": (
            (state.treaty.article_number or "") if reason_code == "a" else ""
        ),
    }
