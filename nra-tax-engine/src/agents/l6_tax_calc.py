"""
L6 Tax Calculation Agent — Aggregates state modifiers and calculates final tax.

Unlike early layers, this Agent does NOT invoke LLMs. All reasoning for
exemption amounts, treaty limits, and residency has already occurred.
This acts strictly as the mathematical orchestrator, binding the outputs
of L3 and L4 to the deterministic TaxCalculator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.functions.tax_math import TaxCalculator

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class TaxCalculationAgent:
    """Deterministic orchestrator for tax computations."""

    def process_tax(self, current_state: ReturnStateObject) -> ReturnStateObject:
        """Apply deductions, execute tax math, and mutate ReturnStateObject.

        Args:
            current_state: The fully populated state object containing
                           final income tallies and treaty entitlements.

        Returns:
            Updated ReturnStateObject with complete liability breakdowns.
        """
        # ==========================================
        # 1. Pull Gross Totals
        # ==========================================
        net_eci = current_state.income.eci_taxable_total
        net_fdap = current_state.income.fdap_taxable_total

        # ==========================================
        # 2. Apply Treaty Deductions
        # ==========================================
        if current_state.treaty.is_eligible:
            category_applied = current_state.treaty.applied_to_category
            exempt_distro = current_state.treaty.exempt_amount_applied

            if category_applied == "teaching_research":
                net_eci = max(0.0, net_eci - exempt_distro)
            elif category_applied == "scholarship":
                net_fdap = max(0.0, net_fdap - exempt_distro)

        # ==========================================
        # 3. Determine Final FDAP Rate
        # ==========================================
        determined_rate = 0.30  # Standard fallback

        # If a treaty fully applies to the FDAP, rate goes to 0% (For our dataset)
        if current_state.treaty.is_eligible and current_state.treaty.applied_to_category == "scholarship":
            # Realistically treaties set specific rates, but for beachhead
            # China and India exempt it fully at 0.0%.
            determined_rate = 0.0
        
        # If no treaty, but student is an F/J/M/Q, FDAP scholarships are 14%
        elif current_state.residency.exempt_visa_type in ["F-1", "J-1", "M-1", "Q-1"]:
            if net_fdap > 0:
                determined_rate = 0.14

        # ==========================================
        # 4. The Deterministic Handoff
        # ==========================================
        calculator = TaxCalculator()
        result = calculator.calculate_tax_liability(
            eci_taxable_income=net_eci,
            fdap_taxable_income=net_fdap,
            fdap_rate=determined_rate,
        )

        # ==========================================
        # 5. State Mutation
        # ==========================================
        current_state.tax.eci_tax_liability = result["eci_tax_liability"]
        current_state.tax.fdap_tax_liability = result["fdap_tax_liability"]
        current_state.tax.total_tax_liability = result["total_tax_liability"]

        current_state.mark_layer_complete("L6")

        return current_state
