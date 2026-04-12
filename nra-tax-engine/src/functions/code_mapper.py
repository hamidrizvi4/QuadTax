# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""
Income Code Mapper — Routes 1042-S income to proper tax treatment.

This deterministic module enforces IRS rules on Effectively Connected Income (ECI)
vs. Fixed, Determinable, Annual, Periodical (FDAP) income categorization,
specifically tackling the complex logic of scholarship/fellowship taxation (Code 16).
"""

from typing import Any, Union


class IncomeCodeMapper:
    """Maps 1042-S income codes to strict tax treatment outcomes.

    These deterministic mapping rules dictate whether income is:
      1. ECI: Taxed at graduated rates with potential deductions.
      2. FDAP: Taxed at flat rates (typically 30%, or 14% for stipends) without deductions.
      3. EXCLUDED: Not subject to US taxation (e.g. bank deposit interest or qualified tuition).
    """

    def __init__(self):
        # Strict mapping definitions sourced from IRS instructions for Form 1042-S

        self.eci_codes = {17, 18, 19, 20, 29, 42}
        self.fdap_codes = {1, 2, 3, 6, 7, 8, 10, 11, 12, 14, 15, 28, 32, 33, 34, 35, 45}

    def route_1042s_income(
        self,
        income_code: Union[int, str],
        gross_amount: float,
        requires_services: bool,
        is_qualified_expense: bool,
    ) -> dict[str, Any]:
        """Route 1042-S gross income based strictly on IRS categorizations.

        Args:
            income_code: The 1042-S 2-digit income type code.
            gross_amount: The gross income reported.
            requires_services: True if this grant/scholarship requires teaching,
                               research, or other services (derived from MCQ).
            is_qualified_expense: True if this grant is for tuition and required
                                  fees only (derived from MCQ).

        Returns:
            A routing dict with 'category', 'taxable_amount', and optionally 'statutory_rate'.
        """
        # Ensure we're working with an integer representations of the code
        # to avoid string matching issues ("01" vs "1" vs 1)
        try:
            code = int(income_code)
        except ValueError:
            raise ValueError(f"Invalid income code format: {income_code}")

        # Rule 1: Exemptions (Bank deposit interest)
        if code == 36:
            return {"category": "EXCLUDED", "taxable_amount": 0.0}

        # Rule 2: The Complex Case — Code 16 (Scholarship/Fellowship)
        if code == 16:
            # Under IRC §117, scholarships used for qualified expenses are tax-free
            if is_qualified_expense:
                return {"category": "EXCLUDED", "taxable_amount": 0.0}

            # If it's not a qualified expense and requires services, it's treated
            # as compensation for services (wages) and therefore ECI.
            if requires_services:
                return {"category": "ECI", "taxable_amount": gross_amount}

            # If it doesn't require services (e.g., standard room & board stipend),
            # it is FDAP income. F/J/M/Q visa holders get a reduced 14% rate
            # instead of the standard 30% flat rate.
            return {
                "category": "FDAP",
                "taxable_amount": gross_amount,
                "statutory_rate": 0.14,
            }

        # Rule 3: ECI Routing (Effectively Connected Income)
        # Includes personal service compensation, artist/athlete incomes, etc.
        if code in self.eci_codes:
            return {"category": "ECI", "taxable_amount": gross_amount}

        # Rule 4: FDAP Routing (Fixed, Determinable, Annual, Periodical)
        # Includes interest, dividends, real property, pensions, etc.
        if code in self.fdap_codes:
            return {"category": "FDAP", "taxable_amount": gross_amount}

        # Fallback for unrecognized 1042-S codes
        raise ValueError(f"Unknown or unsupported 1042-S income code: {code}")
