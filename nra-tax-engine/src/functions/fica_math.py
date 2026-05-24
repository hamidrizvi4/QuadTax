# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""FICA math — exemption check, refund detection, and owed-FICA computation.

Covers three scenarios:

1. **Exempt + FICA wrongly withheld** → Form 843 refund claim (existing path).
2. **Exempt + no FICA withheld** → no action.
3. **Not exempt** → compute the correct FICA the employer should have
   withheld and surface any shortfall on Schedule 2 (resident-alien path).

Reference:
    * IRC §3121(a) — wage base
    * IRC §3121(b)(19) — F/J/M/Q visa exemption
    * IRC §1401(b)(2) and §3101(b)(2) — Additional Medicare Tax (0.9%)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict

from src.database.tax_year import load_year

ZERO = Decimal("0")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class FicaOwedResult:
    """Employer-correct FICA the filer SHOULD have had withheld."""

    social_security_owed: Decimal = ZERO
    medicare_owed: Decimal = ZERO
    additional_medicare_owed: Decimal = ZERO
    total_fica_owed: Decimal = ZERO
    shortfall_vs_withheld: Decimal = ZERO  # > 0 = under-withheld, owe IRS

    def to_dict_floats(self) -> dict:
        return {
            "social_security_owed": float(self.social_security_owed),
            "medicare_owed": float(self.medicare_owed),
            "additional_medicare_owed": float(self.additional_medicare_owed),
            "total_fica_owed": float(self.total_fica_owed),
            "shortfall_vs_withheld": float(self.shortfall_vs_withheld),
        }


class FicaCalculator:
    """Refund detection + actual FICA liability for non-exempt NRA/RA filers."""

    def __init__(self, tax_year: int = 2025) -> None:
        self.tax_year = tax_year
        year = load_year(tax_year)
        self.ss_wage_base = _d(year.fica.social_security["wage_base"])
        self.ss_rate = _d(year.fica.social_security["employee_rate"])
        self.medicare_rate = _d(year.fica.medicare["employee_rate"])  # type: ignore[index]
        self.addl_medicare_rate = _d(year.fica.medicare["additional_medicare_rate"])  # type: ignore[index]
        self.addl_thresholds = {
            k: _d(v)
            for k, v in year.fica.medicare["additional_medicare_thresholds"].items()  # type: ignore[index]
        }
        self.exempt_visas = set(year.fica.fica_exempt_visas)

    # ------------------------------------------------------------------
    # Refund path — existing API, preserved for backward compatibility
    # ------------------------------------------------------------------

    def evaluate_fica_refund(
        self,
        status: str,
        is_exempt_individual: bool,
        raw_ss_withheld: float,
        raw_medicare_withheld: float,
    ) -> Dict[str, Any]:
        """Identify FICA improperly withheld during an F/J/M/Q exempt period."""
        if status == "nonresident_alien" and is_exempt_individual:
            total_fica = _d(raw_ss_withheld) + _d(raw_medicare_withheld)
            return {
                "is_exempt": True,
                "incorrect_ss_withheld": float(raw_ss_withheld),
                "incorrect_medicare_withheld": float(raw_medicare_withheld),
                "requires_form_843": bool(total_fica > 0),
            }
        return {
            "is_exempt": False,
            "incorrect_ss_withheld": 0.0,
            "incorrect_medicare_withheld": 0.0,
            "requires_form_843": False,
        }

    # ------------------------------------------------------------------
    # Owed path — for resident aliens or post-exemption-window NRAs
    # ------------------------------------------------------------------

    def calculate_fica_owed(
        self,
        *,
        wages: float,
        filing_status: str = "single",
        already_withheld_ss: float = 0.0,
        already_withheld_medicare: float = 0.0,
    ) -> FicaOwedResult:
        """Compute the employee-share FICA the filer owes on ``wages``.

        Args:
            wages: Box 5 (Medicare wages) — usually equals box 3 + 401(k) etc.
                For simplicity treat ``wages`` as the Medicare-wage figure.
            filing_status: Used to look up the Additional Medicare threshold.
            already_withheld_ss: Sum of W-2 box 4 across all W-2s.
            already_withheld_medicare: Sum of W-2 box 6 across all W-2s.

        Returns:
            :class:`FicaOwedResult` with the per-component owed amounts.
        """
        result = FicaOwedResult()
        w = _d(wages)

        # Social Security — capped at the wage base.
        ss_taxable = min(w, self.ss_wage_base)
        result.social_security_owed = (ss_taxable * self.ss_rate).quantize(Decimal("0.01"))

        # Regular Medicare — no cap.
        result.medicare_owed = (w * self.medicare_rate).quantize(Decimal("0.01"))

        # Additional Medicare — 0.9% above the filing-status threshold.
        threshold = self.addl_thresholds.get(filing_status, self.addl_thresholds["single"])
        excess = max(ZERO, w - threshold)
        result.additional_medicare_owed = (excess * self.addl_medicare_rate).quantize(
            Decimal("0.01")
        )

        result.total_fica_owed = (
            result.social_security_owed
            + result.medicare_owed
            + result.additional_medicare_owed
        )

        already = _d(already_withheld_ss) + _d(already_withheld_medicare)
        result.shortfall_vs_withheld = max(ZERO, result.total_fica_owed - already)

        return result
