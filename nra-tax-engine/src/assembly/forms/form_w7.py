"""Form W-7 — Application for IRS Individual Taxpayer Identification Number.

Attached to Form 1040-NR when the filer has no SSN and no existing ITIN
(or the ITIN has expired due to 3-year non-use).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def _fmt_birth_date(iso_date: str | None) -> str:
    """Convert an ISO ``YYYY-MM-DD`` date to the 8-character ``MMDDYYYY``
    comb-field format the W-7 PDF's birth-date field expects (no separators —
    the field is a fixed 8-cell comb field, so a 10-character ``MM/DD/YYYY``
    string gets silently truncated by pypdf)."""
    if not iso_date:
        return ""
    parts = iso_date.split("-")
    if len(parts) != 3:
        return iso_date
    year, month, day = parts
    return f"{month}{day}{year}"


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
        "birth_date": _fmt_birth_date(ident.date_of_birth),
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
