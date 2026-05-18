# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""NY state tax math — IT-203 graduated brackets, standard deduction, NYC, Yonkers.

NY uses federal AGI as the starting point but adds back federal treaty
exemptions (NY Publication 88) because NY does NOT honor federal tax
treaties. For nonresidents, the tax is calculated as if the filer were
a NY resident on the full income and then prorated to NY-source income
via the "nonresident-income-percentage" formula on IT-203.

Key NY rules:
    * NY standard deduction is available to nonresident filers (unlike
      federal NRA rules) — $8,000 single TY2025.
    * NY itemized deductions broadly track federal Schedule A but allow
      property tax and mortgage interest (we do not implement NY itemized
      in v1; defaults to standard deduction).
    * NYC tax: only NYC residents; nonresidents owe $0 NYC tax.
    * Yonkers: residents pay 16.675% surcharge on NY state tax;
      nonresidents who earn in Yonkers pay 0.5% on earnings.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from src.database.tax_year import load_year

ZERO = Decimal("0")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class NYTaxResult:
    ny_agi: Decimal = ZERO                 # NY AGI after federal modifications
    ny_treaty_addback: Decimal = ZERO      # Federal treaty exemption added back
    ny_standard_deduction: Decimal = ZERO
    ny_taxable_income: Decimal = ZERO
    ny_tax_resident_basis: Decimal = ZERO  # Tax computed as if NY resident
    ny_source_income: Decimal = ZERO       # NY-source portion (for nonresidents)
    ny_income_percentage: Decimal = ZERO   # Allocation factor for nonresidents
    ny_tax_apportioned: Decimal = ZERO     # Final NY tax (= resident_basis × pct)
    nyc_tax: Decimal = ZERO
    yonkers_tax: Decimal = ZERO
    total_ny_state_local: Decimal = ZERO

    def to_dict_floats(self) -> dict:
        return {
            "ny_agi": float(self.ny_agi),
            "ny_treaty_addback": float(self.ny_treaty_addback),
            "ny_standard_deduction": float(self.ny_standard_deduction),
            "ny_taxable_income": float(self.ny_taxable_income),
            "ny_tax_resident_basis": float(self.ny_tax_resident_basis),
            "ny_source_income": float(self.ny_source_income),
            "ny_income_percentage": float(self.ny_income_percentage),
            "ny_tax_apportioned": float(self.ny_tax_apportioned),
            "nyc_tax": float(self.nyc_tax),
            "yonkers_tax": float(self.yonkers_tax),
            "total_ny_state_local": float(self.total_ny_state_local),
        }


class NYTaxCalculator:
    """Computes NY state, NYC, and Yonkers tax from federal AGI."""

    def __init__(self, tax_year: int = 2025) -> None:
        year = load_year(tax_year)
        if year.ny is None:
            raise FileNotFoundError(f"NY data missing for tax year {tax_year}")
        self.brackets_single: List[dict] = year.ny.get("brackets_single", [])  # type: ignore[arg-type]
        self.standard_deduction: Dict[str, float] = year.ny.get("standard_deduction", {})  # type: ignore[arg-type]
        self.nyc_brackets_single: List[dict] = year.ny.get("nyc_brackets_single", [])  # type: ignore[arg-type]
        self.yonkers: Dict[str, float] = year.ny.get("yonkers", {})  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Bracket math
    # ------------------------------------------------------------------

    def _apply_brackets(self, taxable_income: Decimal, brackets: List[dict]) -> Decimal:
        if taxable_income <= ZERO or not brackets:
            return ZERO
        tax = ZERO
        remaining = taxable_income
        previous_up_to = ZERO
        for row in brackets:
            up_to = row.get("up_to")
            rate = _d(row["rate"])
            if up_to is None:
                chunk = remaining
            else:
                bracket_size = _d(up_to) - previous_up_to
                chunk = min(remaining, bracket_size)
            tax += chunk * rate
            remaining -= chunk
            if up_to is not None:
                previous_up_to = _d(up_to)
            if remaining <= ZERO:
                break
        return tax.quantize(Decimal("0.01"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        *,
        federal_agi: float,
        federal_treaty_exemption: float = 0.0,
        ny_source_income: float = 0.0,
        ny_residency_status: str = "nonresident",
        filing_status: str = "single",
        nyc_resident: bool = False,
        yonkers_resident: bool = False,
        yonkers_nonresident_earnings: float = 0.0,
    ) -> NYTaxResult:
        """Compute NY state + NYC + Yonkers tax.

        Args:
            federal_agi: 1040-NR line 11 figure (federal AGI BEFORE treaty add-back).
            federal_treaty_exemption: Total federal treaty exemption that NY
                does NOT honor — added back to compute NY AGI.
            ny_source_income: NY-source portion of total income (used by
                nonresidents for the income-percentage allocation).
            ny_residency_status: ``resident`` / ``part_year`` / ``nonresident``.
            filing_status: ``single`` / ``mfs`` / ``qss``.
            nyc_resident: True if the filer is a NYC resident (drives NYC tax).
            yonkers_resident: True if the filer is a Yonkers resident.
            yonkers_nonresident_earnings: Earnings in Yonkers by a non-Yonkers
                resident (drives Yonkers nonresident earnings tax).
        """
        result = NYTaxResult()

        result.ny_treaty_addback = _d(federal_treaty_exemption)
        result.ny_agi = _d(federal_agi) + result.ny_treaty_addback

        sd_key = filing_status if filing_status in self.standard_deduction else "single"
        result.ny_standard_deduction = _d(self.standard_deduction.get(sd_key, 8000))

        result.ny_taxable_income = max(ZERO, result.ny_agi - result.ny_standard_deduction)
        result.ny_tax_resident_basis = self._apply_brackets(
            result.ny_taxable_income, self.brackets_single
        )

        # Nonresident allocation (IT-203 nonresident-income-percentage).
        if ny_residency_status == "resident":
            result.ny_source_income = result.ny_agi
            result.ny_income_percentage = _d("1.0")
            result.ny_tax_apportioned = result.ny_tax_resident_basis
        else:
            result.ny_source_income = _d(ny_source_income)
            if result.ny_agi > ZERO:
                result.ny_income_percentage = (
                    result.ny_source_income / result.ny_agi
                ).quantize(Decimal("0.000001"))
            else:
                result.ny_income_percentage = ZERO
            result.ny_tax_apportioned = (
                result.ny_tax_resident_basis * result.ny_income_percentage
            ).quantize(Decimal("0.01"))

        # NYC — only residents.
        if nyc_resident and ny_residency_status in {"resident", "part_year"}:
            result.nyc_tax = self._apply_brackets(
                result.ny_taxable_income, self.nyc_brackets_single
            )
        else:
            result.nyc_tax = ZERO

        # Yonkers.
        if yonkers_resident and ny_residency_status in {"resident", "part_year"}:
            result.yonkers_tax = (
                result.ny_tax_apportioned * _d(self.yonkers.get("resident_surcharge_rate", 0.0))
            ).quantize(Decimal("0.01"))
        elif yonkers_nonresident_earnings > 0:
            result.yonkers_tax = (
                _d(yonkers_nonresident_earnings)
                * _d(self.yonkers.get("nonresident_earnings_rate", 0.0))
            ).quantize(Decimal("0.01"))

        result.total_ny_state_local = (
            result.ny_tax_apportioned + result.nyc_tax + result.yonkers_tax
        )
        return result
