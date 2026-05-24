"""L6 Tax Calculation Agent — Aggregates state modifiers and calculates final tax.

This agent runs NO LLM calls. It pulls net ECI and FDAP totals from
:class:`IncomeState`, subtracts each treaty benefit from the bucket matching
its category, applies the India §21(2) standard-deduction equivalent when
present, derives an effective FDAP rate (treaty-overridden, F/J/M/Q reduced,
or statutory 30%), and hands the figures to the deterministic
:class:`TaxCalculator`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.database.tax_year import load_year
from src.functions.tax_math import TaxCalculator

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


# Categories that reduce the ECI bucket.
_ECI_TREATY_CATEGORIES = {
    "student_personal_services",
    "teaching_research",
    "independent_personal_services",
    "dependent_personal_services",
    "apprentice_trainee",
    "foreign_source_remittance",
}

# Categories that reduce the FDAP bucket.
_FDAP_TREATY_CATEGORIES = {
    "scholarship_fellowship",
}


class TaxCalculationAgent:
    """Deterministic orchestrator for tax computations."""

    def process_tax(self, current_state: "ReturnStateObject") -> "ReturnStateObject":
        """Apply deductions, execute tax math, and mutate ReturnStateObject."""
        net_eci = float(current_state.income.eci_taxable_total)
        net_fdap = float(current_state.income.fdap_taxable_total)

        # --- 1. Apply treaty exemptions per category ---------------------
        india_standard_deduction = False
        scholarship_treaty_exempt_total = 0.0
        for benefit in current_state.treaty.applied_benefits:
            category = benefit.get("category")
            exempt = float(benefit.get("exempt_amount", 0.0) or 0.0)
            if exempt <= 0:
                continue
            if category in _ECI_TREATY_CATEGORIES:
                # India Article 21(2) is modeled as student_personal_services with no $ cap;
                # treat it specially as a standard-deduction equivalent rather than as a
                # blanket wage exemption.
                if (
                    benefit.get("country_iso2") == "IN"
                    and benefit.get("article_id") == "21(2)"
                ):
                    india_standard_deduction = True
                    continue
                net_eci = max(0.0, net_eci - exempt)
            elif category in _FDAP_TREATY_CATEGORIES:
                scholarship_treaty_exempt_total += exempt
                net_fdap = max(0.0, net_fdap - exempt)

        # --- 2. Apply standard deduction (NRA: only India treaty allows it) ---
        if india_standard_deduction:
            year = load_year(2025)
            sd = year.standard_deduction.for_status("single", india_treaty=True)
            net_eci = max(0.0, net_eci - sd)

        # --- 3. Determine effective FDAP rate ----------------------------
        # Statutory default; F/J/M/Q scholarship gets a reduced 14% rate per Schedule NEC.
        if net_fdap > 0 and current_state.residency.exempt_visa_type in {"F-1", "J-1", "M-1", "Q-1"}:
            determined_rate = 0.14
        else:
            determined_rate = 0.30

        # If a scholarship treaty exempted everything (net FDAP == 0 AND we actually
        # exempted scholarship), the effective rate is 0%.
        if net_fdap == 0 and scholarship_treaty_exempt_total > 0:
            determined_rate = 0.0

        # --- 4. Compute liability ----------------------------------------
        calculator = TaxCalculator(tax_year=2025, filing_status="single")
        result = calculator.calculate_tax_liability(
            eci_taxable_income=net_eci,
            fdap_taxable_income=net_fdap,
            fdap_rate=determined_rate,
        )

        # --- 5. State mutation -------------------------------------------
        current_state.tax.eci_tax_liability = result["eci_tax_liability"]
        current_state.tax.fdap_tax_liability = result["fdap_tax_liability"]
        current_state.tax.total_tax_liability = result["total_tax_liability"]

        current_state.mark_layer_complete("L6")
        return current_state
