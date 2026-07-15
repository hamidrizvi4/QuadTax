"""Form W-7 — Application for IRS Individual Taxpayer Identification Number.

Attached to Form 1040-NR when the filer has no SSN and no existing ITIN
(or the ITIN has expired due to 3-year non-use).

Field positions/labels below were verified against the real vendored
``assets/templates/2025/fw7.pdf`` by walking its widget annotations
(fully-qualified field name, real ``/AP /N`` export states, and ``/Rect``
position) and cross-referencing against the printed text extracted with
per-word (x, y) coordinates — not the AcroForm's linear field order, which
does not track visual/line order on this multi-column IRS form.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def _fmt_comb_date(iso_date: str | None) -> str:
    """Convert an ISO ``YYYY-MM-DD`` date to the 8-character ``MMDDYYYY``
    comb-field format this PDF's date fields expect (no separators — the
    fields are fixed 8-cell comb fields, so a 10-character ``MM/DD/YYYY``
    string gets silently truncated by pypdf). Used for line 4's date of
    birth, and line 6d's "date of entry into the United States"; both are
    real 8-cell ``/MaxLen 8`` comb fields per a raw widget-annotation dump
    of the vendored template."""
    if not iso_date:
        return ""
    parts = iso_date.split("-")
    if len(parts) != 3:
        return iso_date
    year, month, day = parts
    return f"{month}{day}{year}"


_REASON_LETTERS = ["a", "b", "c", "d", "e", "f", "g", "h"]


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity

    # The specific applied treaty benefit (if any) that actually triggers
    # Form 8833 — reason "a" needs THAT benefit's country/article, not the
    # TreatyState scalar "primary (largest-exemption)" fields, which can
    # point at a different article for multi-article-treaty countries
    # (e.g. a filer with both a China Art. 20(b) scholarship exemption and
    # a smaller Art. 20(c) wage exemption, only one of which needs 8833).
    treaty_8833_benefit = next(
        (b for b in state.treaty.applied_benefits if b.get("requires_form_8833")),
        None,
    )

    reason_code = "f"  # NRA student/professor — default
    if treaty_8833_benefit is not None:
        reason_code = "a"  # NRA required to obtain ITIN to claim treaty benefit
    elif not (state.residency.exempt_visa_type or "").startswith(("F", "J", "M", "Q")):
        reason_code = "b"  # NRA filing a US tax return (generic)

    is_renewal = bool((state.itin_eligibility or {}).get("is_renewal", False))

    reason_map = {f"reason_{letter}": (letter == reason_code) for letter in _REASON_LETTERS}
    if reason_code == "a":
        # Form W-7's own printed instructions for box a are unconditional:
        # "Nonresident alien required to get an ITIN to claim tax treaty
        # benefit (you must also check and complete box h (see
        # instructions))" — verified against the real extracted PDF text.
        # We check box h here since that's derivable from the same
        # reason-a determination, but deliberately do NOT fill in box h's
        # free-text "Other" explanation (f1_04 on the real PDF): that line
        # wants a specific numbered IRS "Exception" category (e.g.
        # "Exception 1(d)"), which this engine does not compute, and
        # guessing one risks asserting a legal exception the filer may not
        # actually qualify for. A human preparer must complete that line.
        reason_map["reason_h"] = True

    treaty_country = ""
    treaty_article = ""
    if reason_code == "a" and treaty_8833_benefit is not None:
        treaty_country = (
            treaty_8833_benefit.get("country_iso2")
            or state.treaty.country
            or ident.country_of_tax_residence
            or ""
        )
        treaty_article = (
            treaty_8833_benefit.get("article_id") or state.treaty.article_number or ""
        )

    # Line 6e "Have you previously received an ITIN or an IRSN?" — this
    # engine only ever attaches Form W-7 when itin_eligibility.needs_w7 is
    # True, which is either a first-time application (is_renewal False) or
    # a renewal of an existing-but-expired ITIN (is_renewal True), so the
    # Yes/No answer maps 1:1 to is_renewal. When renewing, line 6f wants
    # the previously-issued ITIN split into its printed XXX-XX-XXXX comb
    # groups (real /MaxLen 3/2/4 on the vendored PDF) and the name it was
    # issued under — we use the filer's current legal name since no
    # separate "name ITIN was issued under" field exists in state (unlike
    # line 1b "name at birth if different", this line has no "if
    # different" qualifier, so the current name is a reasonable value
    # rather than a fabrication).
    prior_itin_digits = "".join(ch for ch in (ident.itin or "") if ch.isdigit())
    has_prior_itin = is_renewal and bool(prior_itin_digits)

    return {
        "reason_code": reason_code,  # kept for any consumer reading the raw letter
        **reason_map,
        "application_type_new": not is_renewal,
        "application_type_renewal": is_renewal,
        # Line 1a is three SEPARATE boxes (First / Middle / Last name) on
        # the real PDF, not one combined field — verified via widget
        # /Rect positions matching the "First name / Middle name / Last
        # name" column labels above them.
        "first_name": ident.first_name,
        "middle_initial": ident.middle_initial,
        "last_name": ident.last_name,
        # Line 1b "Name at birth if different" is intentionally left
        # unmapped: the real PDF instructs filers to leave it blank unless
        # the name at birth differs from line 1a, and state has no
        # dedicated birth-name field to detect that — re-asserting the
        # current name here would misrepresent "no change" as "here is
        # your birth name."
        "mailing_address_line1": ident.us_address_line1,
        "mailing_city_state_zip": f"{ident.us_city}, {ident.us_state} {ident.us_zip}".strip(", "),
        "foreign_address_line1": ident.foreign_address_line1,
        "foreign_address_country": ident.foreign_country,
        "birth_date": _fmt_comb_date(ident.date_of_birth),
        # No dedicated "country of birth" field exists in state (only
        # foreign residence country, citizenship, and tax-residence
        # country) — foreign_country is reused here as the best available
        # proxy. Usually correct for this product's typical filer
        # (international student/scholar whose home address matches their
        # birth country) but can diverge for naturalized citizens or
        # filers whose foreign correspondence address isn't their
        # birthplace. Flagged as a known data-model gap, not fixed here
        # since no better-justified source exists.
        "country_of_birth": ident.foreign_country,
        "country_of_citizenship": ident.country_of_citizenship,
        # Line 6c "Type of U.S. visa (if any), number, and expiration
        # date" is a single combined text field on the real PDF; we only
        # have the visa category (e.g. "F-1"), not its number/expiration,
        # so only the category is written — partial-but-real data rather
        # than a fabricated number/date.
        "visa_type": state.residency.exempt_visa_type or "",
        # Line 6d "Date of entry into the United States" — real 8-cell
        # comb field, same MMDDYYYY format as birth_date.
        "us_entry_date": _fmt_comb_date(state.residency.first_us_entry_date),
        "passport_number": ident.passport_number,
        "passport_country": ident.passport_country,
        # Line 6d "Identification document(s) submitted" — this engine
        # only ever collects passport data (no driver's license/USCIS
        # document intake), so the Passport checkbox is checked exactly
        # when we actually have a passport number to show; the other
        # three checkboxes (driver's license/State ID, USCIS
        # documentation, Other) have no backing data and are left unset.
        "id_doc_passport": bool(ident.passport_number),
        "applicant_signature_name": f"{ident.first_name} {ident.last_name}".strip(),
        "applicant_phone": ident.daytime_phone,
        "treaty_country_when_reason_a": treaty_country,
        "treaty_article_when_reason_a": treaty_article,
        "previously_received_itin_no": not is_renewal,
        "previously_received_itin_yes": is_renewal,
        "prior_itin_group1": prior_itin_digits[0:3] if has_prior_itin else "",
        "prior_itin_group2": prior_itin_digits[3:5] if has_prior_itin else "",
        "prior_itin_group3": prior_itin_digits[5:9] if has_prior_itin else "",
        "prior_itin_name_first": ident.first_name if has_prior_itin else "",
        "prior_itin_name_middle": ident.middle_initial if has_prior_itin else "",
        "prior_itin_name_last": ident.last_name if has_prior_itin else "",
    }
