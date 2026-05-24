"""Form 1040-NR (US Nonresident Alien Income Tax Return).

Maps the finalized :class:`ReturnStateObject` to the AcroForm field names
on the 2024-revision Form 1040-NR (closest available to TY2025; refresh
when the IRS publishes the 2025 revision).

Field names follow the convention used by the IRS draft AcroForm metadata:
``f1_X[0]`` for text fields and ``c1_X[0]`` for checkboxes. Line numbers
mirror the published form. When the TY2025 form is published, run
``pdftk f1040nr.pdf dump_data_fields`` to refresh the keys in
``assets/templates/2025/1040nr_fields.json``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


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

    # India treaty Article 21(2) flips on the standard-deduction path.
    has_india_std_ded = any(
        b.get("country_iso2") == "IN" and b.get("article_id") == "21(2)"
        for b in treaty.applied_benefits
    )
    chosen_label = state.sch_a.get("chosen_deduction_label", "")
    standard_deduction_used = state.sch_a.get("standard_deduction_used", 0.0)
    itemized_total = state.sch_a.get("total", 0.0)
    deduction_amount = standard_deduction_used if chosen_label == "standard" else itemized_total

    # AMTI and other Schedule-2 lines flow into 1040-NR line 23a/23b.
    amt_owed = state.tax.amt_owed if hasattr(state.tax, "amt_owed") else 0.0

    # Withholding sources by line.
    wh = state.withholding_report or {}

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
        # Filing status checkboxes (1 = Single resident of Canada/Mexico/dual-status; 2 = Other single NRA)
        "filing_status_single": True if ident.filing_status == "single" else False,
        "filing_status_mfs": True if ident.filing_status == "mfs" else False,
        "filing_status_qss": True if ident.filing_status == "qss" else False,
        # Line 1a — total W-2 wages
        "line_1a_wages": _fmt_money(income.total_w2_wages),
        # Line 1k — treaty-exempt wages subtotal (sum across all wage-category benefits)
        "line_1k_treaty_exempt_wages": _fmt_money(
            sum(
                float(b.get("exempt_amount", 0.0))
                for b in treaty.applied_benefits
                if b.get("category")
                in {
                    "student_personal_services",
                    "teaching_research",
                    "independent_personal_services",
                    "dependent_personal_services",
                    "foreign_source_remittance",
                }
                # Exclude India 21(2) which is a standard-deduction path, not a wage exemption.
                and not (b.get("country_iso2") == "IN" and b.get("article_id") == "21(2)")
            )
        ),
        # Line 1z — net wages after treaty subtotal
        "line_1z_total_wages_net": _fmt_money(
            max(0.0, float(income.total_w2_wages) - float(_unwrap(income, "eci_treaty_subtract", 0.0)))
        ),
        # Line 8 — scholarship/fellowship grants taxable (after §117 exclusion and treaty)
        "line_8_scholarship_taxable": _fmt_money(income.fdap_taxable_total),
        # Line 9 — total income
        "line_9_total_income": _fmt_money(
            float(income.total_w2_wages) + float(income.fdap_taxable_total)
        ),
        # Line 11 — AGI (same as Line 9 for most NRA students; no above-line adjustments)
        "line_11_agi": _fmt_money(
            float(income.total_w2_wages) + float(income.fdap_taxable_total)
        ),
        # Line 12 — deduction (itemized OR India standard)
        "line_12_deduction": _fmt_money(deduction_amount),
        # Line 15 — taxable income
        "line_15_taxable_income": _fmt_money(
            max(0.0, float(income.eci_taxable_total) - float(treaty.exempt_amount_applied))
        ),
        # Line 16 — tax (from tables)
        "line_16_tax": _fmt_money(tax.eci_tax_liability),
        # Line 23a — AMT (Form 6251)
        "line_23a_amt": _fmt_money(amt_owed),
        # Line 23b — total other taxes from Schedule 2
        "line_23b_other_taxes": _fmt_money(0.0),
        # Line 24 — total tax (regular + FDAP from Sch NEC + AMT)
        "line_24_total_tax": _fmt_money(tax.total_tax_liability + float(amt_owed or 0.0)),
        # Line 25a — federal withholding from W-2 box 2
        "line_25a_w2_withholding": _fmt_money(wh.get("federal_w2", 0.0)),
        # Line 25b — federal withholding from 1042-S box 7a (Ch 3 + Ch 4)
        "line_25b_1042s_withholding": _fmt_money(
            float(wh.get("federal_1042s_ch3", 0.0))
            + float(wh.get("federal_1042s_ch4", 0.0))
        ),
        # Line 25c — federal withholding from 1099 forms
        "line_25c_1099_withholding": _fmt_money(wh.get("federal_1099", 0.0)),
        # Line 26 — estimated tax payments
        "line_26_estimated_payments": _fmt_money(wh.get("federal_estimated_payments", 0.0)),
        # Line 32 — total payments
        "line_32_total_payments": _fmt_money(tax.total_withholding_credits),
        # Line 33 — refund (positive) when payments > total tax
        "line_33_refund": _fmt_money(max(0.0, -float(tax.refund_or_owed))),
        # Line 35a — direct deposit amount (echoes Line 33 unless filer opted out)
        "line_35a_direct_deposit_refund": _fmt_money(max(0.0, -float(tax.refund_or_owed))),
        # Line 37 — amount you owe
        "line_37_owed": _fmt_money(max(0.0, float(tax.refund_or_owed))),
        # Signature block
        "signature_occupation": ident.occupation,
        "signature_daytime_phone": ident.daytime_phone,
        "signature_email": ident.email,
    }
    return mapping


def _unwrap(model, attr: str, default):
    """Lookup an attr on a Pydantic model with a default fallback."""
    return getattr(model, attr, default)
