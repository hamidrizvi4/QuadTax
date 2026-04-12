# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""
Tax Math Module — Progressively calculates tax liabilities.

Implements pure deterministic math for ECI graduated taxation and FDAP flat
taxation. Expects pre-processed net income (meaning agents must apply 
deductions and treaty exemptions upstream).
"""

import json
from pathlib import Path
from typing import Dict, Union


class TaxCalculator:
    """Calculates tax liabilities progressively without LLM inference."""

    def __init__(self, db_path: Union[str, Path, type(None)] = None):
        """Initialize the tax calculator and load the progressive brackets.

        Args:
            db_path: Optional path to the tax_brackets.json dependency.
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "database" / "tax_brackets.json"

        with open(db_path, "r", encoding="utf-8") as f:
            self.brackets = json.load(f)

    def calculate_tax_liability(
        self, eci_taxable_income: float, fdap_taxable_income: float, fdap_rate: float
    ) -> Dict[str, float]:
        """Apply sequential bracket math to ECI and flat rates to FDAP.

        Args:
            eci_taxable_income: Net ECI to be passed through graduated brackets.
            fdap_taxable_income: Net FDAP to be taxed firmly at fdap_rate.
            fdap_rate: The statutory or treaty-overridden flat rate (e.g. 0.30 or 0.14).

        Returns:
            Dictionary subset matching TaxCalculatedState liability fields.
        """
        # ==========================================
        # 1. FDAP Taxation (Flat Rate)
        # ==========================================
        fdap_tax = fdap_taxable_income * fdap_rate

        # ==========================================
        # 2. ECI Taxation (Progressive/Graduated)
        # ==========================================
        eci_tax = 0.0
        remaining_income = eci_taxable_income
        previous_bracket_up_to = 0.0

        for bracket in self.brackets:
            if remaining_income <= 0:
                break

            up_to = bracket.get("up_to")
            rate = bracket["rate"]

            if up_to is not None:
                bracket_size = up_to - previous_bracket_up_to
                chunk = min(remaining_income, bracket_size)
            else:
                # Null upper limit -> tax everything remaining
                chunk = remaining_income

            eci_tax += chunk * rate
            remaining_income -= chunk

            if up_to is not None:
                previous_bracket_up_to = up_to

        # ==========================================
        # 3. IRS Rounding Rules (Nearest whole dollar)
        # ==========================================
        eci_tax_rounded = float(round(eci_tax))
        fdap_tax_rounded = float(round(fdap_tax))

        return {
            "eci_tax_liability": eci_tax_rounded,
            "fdap_tax_liability": fdap_tax_rounded,
            "total_tax_liability": eci_tax_rounded + fdap_tax_rounded,
        }
