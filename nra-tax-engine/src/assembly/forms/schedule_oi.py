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

    treaty_rows: List[dict] = []
    for benefit in treaty.applied_benefits:
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
                "amount_prior_years": 0.0,  # intake-derived; placeholder
            }
        )

    return {
        # A — country of citizenship
        "item_A_country_citizenship": ident.country_of_citizenship,
        # B — country of tax residence
        "item_B_country_tax_residence": ident.country_of_tax_residence,
        # C — visa type
        "item_C_visa_type": residency.exempt_visa_type or "",
        # D — immigration status change? (intake-derived; default no)
        "item_D_immigration_status_change": False,
        # E — were you a US resident in a prior year?
        "item_E_prior_year_resident": False,
        # F — first year you held this visa
        "item_F_first_year_in_visa": (
            state.tax_year - residency.years_in_exempt_status + 1
            if residency.years_in_exempt_status > 0
            else state.tax_year
        ),
        # G — days in US during current and prior 2 years
        "item_G_days_current_year": residency.spt_days_current_year,
        "item_G_days_year_minus_1": 0,  # intake-derived
        "item_G_days_year_minus_2": 0,  # intake-derived
        # H — filed 1040 in prior year?
        "item_H_filed_1040_prior_year": False,
        # I — §6013(g)/(h) election in effect?
        "item_I_6013_election": False,
        # J — §871(d) election (real property treated as ECI)?
        "item_J_871d_election": False,
        # K — gifts/bequests over $100,000 from foreign person (Form 3520)?
        "item_K_large_foreign_gifts": False,
        # L — Treaty benefit table (one row per applied benefit)
        "item_L_treaty_rows": treaty_rows,
        # M — Closer Connection Exception (Form 8840)?
        "item_M_closer_connection": False,
        # Cross-references to top-form income lines
        "_total_treaty_exempt_amount": float(
            sum(r["amount_this_year"] for r in treaty_rows)
        ),
        "_total_income_for_reconciliation": float(
            income.total_w2_wages + income.fdap_taxable_total
        ),
    }
