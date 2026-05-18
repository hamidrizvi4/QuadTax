# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Alternative Minimum Tax (AMT) — Form 6251 math.

For most NRA students AMT will be zero; the calculator must still run for
compliance closure (Form 6251 line 11 may need to be attached even if zero).

Steps (per Form 6251, 2024 instructions, simplified):

    1. Start with taxable income (1040-NR line 15).
    2. Add back AMT preferences (rare for students; default 0 in v1).
    3. Subtract the AMT exemption, phased out above the threshold.
    4. Apply the 26% / 28% kink.
    5. Subtract the regular tax; the excess (if positive) is the AMT.

Reference: IRC §55–§59; Form 6251 instructions; Rev. Proc. 2024-40.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.database.tax_year import load_year

ZERO = Decimal("0")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class AMTResult:
    amti: Decimal = ZERO          # Alternative Minimum Taxable Income
    exemption: Decimal = ZERO     # After phase-out
    tentative_minimum_tax: Decimal = ZERO  # Pre-comparison TMT
    regular_tax_for_amt: Decimal = ZERO
    amt_owed: Decimal = ZERO      # max(0, TMT − regular_tax)
    binds: bool = False           # True iff amt_owed > 0

    def to_dict_floats(self) -> dict:
        return {
            "amti": float(self.amti),
            "exemption": float(self.exemption),
            "tentative_minimum_tax": float(self.tentative_minimum_tax),
            "regular_tax_for_amt": float(self.regular_tax_for_amt),
            "amt_owed": float(self.amt_owed),
            "binds": self.binds,
        }


class AMTCalculator:
    """Form 6251 math driven by year-keyed parameters."""

    def __init__(self, tax_year: int = 2025) -> None:
        self.tax_year = tax_year
        year = load_year(tax_year)
        self.exemption_by_status = {k: _d(v) for k, v in year.amt.exemption.items()}
        self.phaseout_threshold = {
            k: _d(v) for k, v in year.amt.phaseout_threshold.items()
        }
        self.kink = {k: _d(v) for k, v in year.amt.rate_kink.items()}
        self.lower_rate = _d(year.amt.rates["lower"])
        self.upper_rate = _d(year.amt.rates["upper"])

    def compute(
        self,
        *,
        taxable_income: float,
        regular_tax: float,
        filing_status: str = "single",
        preferences: float = 0.0,
    ) -> AMTResult:
        """Compute AMT owed (if any) for the filer.

        Args:
            taxable_income: 1040-NR line 15 (taxable income before tax).
            regular_tax: 1040-NR line 16 (regular tax, before credits).
            filing_status: ``single`` / ``mfs`` / ``qss``.
            preferences: Sum of preference items / AMT adjustments (rare for
                students; default 0).
        """
        result = AMTResult()

        # AMTI: taxable income + preferences. Form 6251 also adds back the
        # standard deduction in some cases, but for NRA filers using the
        # NRA path (no SD by default) this is a no-op.
        result.amti = _d(taxable_income) + _d(preferences)

        # Exemption (phased out by 25¢ per $1 above the threshold).
        base_exemption = self.exemption_by_status.get(
            filing_status, self.exemption_by_status["single"]
        )
        threshold = self.phaseout_threshold.get(
            filing_status, self.phaseout_threshold["single"]
        )
        excess = max(ZERO, result.amti - threshold)
        phaseout = (excess * _d("0.25")).quantize(Decimal("0.01"))
        result.exemption = max(ZERO, base_exemption - phaseout)

        # Tentative AMTI after exemption.
        amti_after_ex = max(ZERO, result.amti - result.exemption)

        # 26% on the first $kink, 28% on the rest.
        kink_amount = self.kink.get(filing_status, self.kink["single"])
        if amti_after_ex <= kink_amount:
            tmt = amti_after_ex * self.lower_rate
        else:
            tmt = (
                kink_amount * self.lower_rate
                + (amti_after_ex - kink_amount) * self.upper_rate
            )
        result.tentative_minimum_tax = tmt.quantize(Decimal("0.01"))

        result.regular_tax_for_amt = _d(regular_tax)
        result.amt_owed = max(
            ZERO, result.tentative_minimum_tax - result.regular_tax_for_amt
        ).quantize(Decimal("0.01"))
        result.binds = result.amt_owed > ZERO

        return result
