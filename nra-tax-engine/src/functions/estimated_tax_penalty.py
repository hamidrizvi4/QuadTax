# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Estimated tax penalty (Form 2210) — Phase-3 worst-case stub.

For v1 the engine returns a worst-case penalty estimate or zero and lets
the IRS compute the actual penalty in its notice (industry-standard
practice — see plan section "Trade-offs explicitly made"). The interface
matches what a full implementation would produce so callers do not need
to change.

Safe-harbor rules (IRC §6654):
    * No penalty if total tax minus withholding is < $1,000.
    * No penalty if withholding + estimated payments ≥ 90% of current
      year's tax.
    * No penalty if withholding + estimated payments ≥ 100% of prior
      year's tax (110% if prior-year AGI > $150k / $75k MFS).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")
SAFE_HARBOR_DE_MINIMIS = Decimal("1000")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class EstimatedTaxPenaltyResult:
    safe_harbor_met: bool = False
    safe_harbor_reason: str = ""
    penalty_amount: Decimal = ZERO  # Worst-case estimate; IRS will compute the precise figure
    must_attach_form_2210: bool = False

    def to_dict_floats(self) -> dict:
        return {
            "safe_harbor_met": self.safe_harbor_met,
            "safe_harbor_reason": self.safe_harbor_reason,
            "penalty_amount": float(self.penalty_amount),
            "must_attach_form_2210": self.must_attach_form_2210,
        }


def evaluate(
    *,
    current_year_total_tax: float,
    total_withholding_and_estimated: float,
    prior_year_total_tax: float = 0.0,
    prior_year_agi_over_150k: bool = False,
) -> EstimatedTaxPenaltyResult:
    """Apply the §6654 safe-harbor rules; return a worst-case penalty estimate."""
    result = EstimatedTaxPenaltyResult()

    current_tax = _d(current_year_total_tax)
    paid = _d(total_withholding_and_estimated)
    underpayment = current_tax - paid

    if underpayment < SAFE_HARBOR_DE_MINIMIS:
        result.safe_harbor_met = True
        result.safe_harbor_reason = "Underpayment is below the $1,000 de minimis threshold."
        return result

    # 90% of current year
    if paid >= current_tax * _d("0.90"):
        result.safe_harbor_met = True
        result.safe_harbor_reason = "Withholding ≥ 90% of current-year tax."
        return result

    # 100% (or 110% for high-income) of prior year
    prior = _d(prior_year_total_tax)
    if prior > ZERO:
        threshold_pct = _d("1.10") if prior_year_agi_over_150k else _d("1.00")
        if paid >= prior * threshold_pct:
            result.safe_harbor_met = True
            result.safe_harbor_reason = (
                f"Withholding ≥ {int(threshold_pct * 100)}% of prior-year tax."
            )
            return result

    # Not safe-harbored — IRS will compute the actual penalty. We surface the
    # underpayment amount as a worst-case so the filer knows to expect a notice.
    result.must_attach_form_2210 = True
    result.penalty_amount = underpayment  # placeholder; IRS computes the rate-blended figure
    result.safe_harbor_reason = (
        "No safe harbor met; Form 2210 attached. IRS will compute the precise "
        "penalty using underpayment timing and the §6621 rates."
    )
    return result
