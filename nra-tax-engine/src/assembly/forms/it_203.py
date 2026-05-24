"""Form IT-203 — NY Nonresident / Part-Year Resident Income Tax Return.

Maps the finalized :class:`ReturnStateObject` to the AcroForm field names
on the NY DTF IT-203 form. Field names follow the convention published in
the NYS DTF AcroForm drafts.
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
    ny = state.ny

    return {
        # Header — identity
        "tax_year": state.tax_year,
        "first_name_mi": f"{ident.first_name} {ident.middle_initial}".strip(),
        "last_name": ident.last_name,
        "tin": ident.primary_tin,
        "us_address_line1": ident.us_address_line1,
        "us_city": ident.us_city,
        "us_state": ident.us_state,
        "us_zip": ident.us_zip,
        # Filing status — NY single = code 1
        "filing_status_code": 1 if ident.filing_status == "single" else 3,
        # Residency status
        "is_nonresident": ny.residency_status == "nonresident",
        "is_part_year_resident": ny.residency_status == "part_year",
        "is_full_year_resident": ny.residency_status == "resident",
        # Line 1 — federal AGI (NY uses this as the starting point)
        "line_1_federal_agi": _fmt_money(ny.ny_agi - ny.ny_treaty_addback),
        # Line 21 — additions: federal treaty exemption added back per NY Pub 88
        "line_21_treaty_addback": _fmt_money(ny.ny_treaty_addback),
        # Line 31 — NY AGI
        "line_31_ny_agi": _fmt_money(ny.ny_agi),
        # Line 33 — standard deduction
        "line_33_standard_deduction": _fmt_money(ny.ny_standard_deduction),
        # Line 37 — NY taxable income
        "line_37_ny_taxable_income": _fmt_money(ny.ny_taxable_income),
        # Line 38 — NY State tax on the taxable income (resident basis)
        "line_38_ny_tax_resident_basis": _fmt_money(ny.ny_tax_resident_basis),
        # Line 45 — income percentage (from IT-203-B) for nonresident allocation
        "line_45_income_percentage": (
            f"{ny.ny_income_percentage * 100:.4f}"
            if ny.residency_status != "resident"
            else "100.0000"
        ),
        # Line 46 — apportioned NY tax = line 38 × line 45
        "line_46_apportioned_ny_tax": _fmt_money(ny.ny_tax_apportioned),
        # NYC residency-driven lines
        "line_50_nyc_resident_tax": _fmt_money(ny.nyc_tax),
        # Yonkers tax
        "line_51_yonkers_tax": _fmt_money(ny.yonkers_tax),
        # Line 60 — total NY State + NYC + Yonkers tax
        "line_60_total_ny_state_local_tax": _fmt_money(ny.total_ny_state_local),
        # Line 62 — total NY withholding
        "line_62_ny_withholding": _fmt_money(ny.ny_withholding),
        # Line 63 — NYC withholding
        "line_63_nyc_withholding": _fmt_money(ny.nyc_withholding),
        # Line 67 — total payments
        "line_67_total_payments": _fmt_money(ny.ny_withholding + ny.nyc_withholding),
        # Line 68 — amount overpaid (refund)
        "line_68_overpaid_refund": _fmt_money(max(0.0, -ny.ny_refund_or_owed)),
        # Line 70 — amount you owe
        "line_70_amount_owed": _fmt_money(max(0.0, ny.ny_refund_or_owed)),
        "signature_occupation": ident.occupation,
        "signature_phone": ident.daytime_phone,
        "_residency_reason": ny.residency_reason,
    }
