"""Schedule OI (1040-NR) — Other Information. ALWAYS required.

Captures the demographic information the IRS uses to validate residency,
treaty claims, prior-year filings, and elections. Most NRA tax software
gets this wrong by omitting Item L (treaty article table); QuadTax
populates it from :attr:`TreatyState.applied_benefits`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    residency = state.residency
    treaty = state.treaty
    income = state.income
    elections = state.elections

    treaty_rows: List[dict] = []
    for i, benefit in enumerate(treaty.applied_benefits):
        # India Article 21(2) is a standard-DEDUCTION equivalent claimed on
        # 1040-NR line 12, NOT an income exemption — it does not belong in the
        # Item L treaty-exempt-income table (listing the full wages here would
        # wrongly imply they were exempt from tax).
        if benefit.get("country_iso2") == "IN" and benefit.get("article_id") == "21(2)":
            continue
        treaty_rows.append(
            {
                "country": benefit.get("country_name", ""),
                "article": benefit.get("article_id", ""),
                "income_code": "",  # populated by L3 if needed
                "amount_this_year": float(benefit.get("exempt_amount", 0.0)),
                # Filer-reported prior-year claim total is display-only and
                # not itemized per benefit — attach it to the first row only
                # so it doesn't visually imply a per-article prior amount.
                "amount_prior_years": (
                    float(treaty.prior_year_treaty_claim_total) if i == 0 else 0.0
                ),
            }
        )

    return {
        # A — country of citizenship
        "item_A_country_citizenship": ident.country_of_citizenship,
        # B — country of tax residence
        "item_B_country_tax_residence": ident.country_of_tax_residence,
        # C — visa type
        "item_C_visa_type": residency.exempt_visa_type or "",
        # D — immigration status change? (no intake source yet; default no)
        "item_D_immigration_status_change": False,
        # E — were you a US resident in a prior year?
        "item_E_prior_year_resident": residency.prior_year_residency_status == "resident_alien",
        # F — first year you held this visa
        "item_F_first_year_in_visa": (
            state.tax_year - residency.years_in_exempt_status + 1
            if residency.years_in_exempt_status > 0
            else state.tax_year
        ),
        # G — days in US during current and prior 2 years (raw physical
        # presence, populated by L1 from I-94 OCR — same source as Form 8843).
        "item_G_days_current_year": residency.days_present_current_year,
        "item_G_days_year_minus_1": residency.days_present_year_minus_1,
        "item_G_days_year_minus_2": residency.days_present_year_minus_2,
        # H — filed 1040 in prior year?
        "item_H_filed_1040_prior_year": state.extras.filed_previous_federal_return,
        # I — §6013(g)/(h) election in effect?
        "item_I_6013_election": (
            elections.section_6013g_election or elections.section_6013h_election
        ),
        # J — §871(d) election (real property treated as ECI)?
        "item_J_871d_election": elections.section_871d_election,
        # K — gifts/bequests over $100,000 from foreign person (Form 3520)?
        "item_K_large_foreign_gifts": elections.large_foreign_gifts_over_100k,
        # L — Treaty benefit table (one row per applied benefit)
        "item_L_treaty_rows": treaty_rows,
        # M — Closer Connection Exception (Form 8840)?
        "item_M_closer_connection": elections.closer_connection_exception_claimed,
        # Cross-references to top-form income lines
        "_total_treaty_exempt_amount": float(
            sum(r["amount_this_year"] for r in treaty_rows)
        ),
        "_total_income_for_reconciliation": float(
            income.total_w2_wages + income.fdap_taxable_total
        ),
    }
