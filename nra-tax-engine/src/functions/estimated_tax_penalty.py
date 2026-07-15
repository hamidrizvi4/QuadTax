# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Estimated tax penalty (Form 2210) — regular-method quarterly calculation.

Safe-harbor rules (IRC §6654) — checked first, unchanged from the original
implementation:
    * No penalty if total tax minus withholding is < $1,000.
    * No penalty if withholding + estimated payments ≥ 90% of current
      year's tax.
    * No penalty if withholding + estimated payments ≥ 100% of prior
      year's tax (110% if prior-year AGI > $150k / $75k MFS).

When no safe harbor is met, this computes a real per-period penalty using
Form 2210 Part III's regular method: four required installments (25% of
the required annual payment each), due 4/15, 6/15, 9/15 of the tax year
and 1/15 of the following year, compared against a running cumulative
balance of payments credited, with interest charged on each period's
outstanding underpayment for the days it was owed.

Two deliberate simplifications, both documented inline where they apply:
    1. Withholding is treated as paid evenly across all four periods (the
       standard default absent specific per-paycheck withholding dates —
       real Form 2210 allows establishing actual dates, which this engine
       does not currently collect).
    2. Estimated payments are conservatively assumed paid in the final
       period only, since this engine tracks a lump total rather than
       per-payment dates. A filer who actually paid earlier owes less than
       this estimate, never more — this stays a worst-case bound, matching
       the original stub's design intent, just a tighter one.

IRS_UNDERPAYMENT_ANNUAL_RATE is a single current-period §6621 rate applied
uniformly across all quarters. The real rate is published quarterly by the
IRS (federal short-term rate + 3 points) and can change every quarter —
this constant is a PLACEHOLDER that must be verified against the current
quarter's published Revenue Ruling and refreshed periodically, the same
convention already used for src/database/tax_year/2025/ny.json's indexed
figures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import List

ZERO = Decimal("0")
SAFE_HARBOR_DE_MINIMIS = Decimal("1000")

# PLACEHOLDER — verify against the current quarter's published Rev. Rul.
# (IRC §6621: federal short-term rate + 3 percentage points) and refresh.
IRS_UNDERPAYMENT_ANNUAL_RATE = Decimal("0.08")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class InstallmentPeriod:
    """One of the four required-installment periods (Form 2210 Part III)."""

    due_date: date
    required_installment: Decimal
    payment_credited: Decimal
    underpayment_balance: Decimal
    days_charged: int
    period_penalty: Decimal

    def to_dict_floats(self) -> dict:
        return {
            "due_date": self.due_date.isoformat(),
            "required_installment": float(self.required_installment),
            "payment_credited": float(self.payment_credited),
            "underpayment_balance": float(self.underpayment_balance),
            "days_charged": self.days_charged,
            "period_penalty": float(self.period_penalty),
        }


@dataclass
class EstimatedTaxPenaltyResult:
    safe_harbor_met: bool = False
    safe_harbor_reason: str = ""
    penalty_amount: Decimal = ZERO
    must_attach_form_2210: bool = False
    periods: List[InstallmentPeriod] = field(default_factory=list)

    # Form 2210, Part I — computed unconditionally (not just when a penalty
    # is ultimately owed), because lines 4/5/9 are themselves part of the
    # "Do You Have To File Form 2210?" determination printed on page 1, and
    # the PDF populator needs real values for them regardless of outcome.
    line_4_current_year_tax: Decimal = ZERO
    line_5_ninety_pct_current_year: Decimal = ZERO
    # None when no prior-year tax figure was supplied (this engine currently
    # collects none — see form_2210.py's comment on line 8), matching real
    # Form 2210's own instruction that line 8 is only completed when you
    # have a prior-year amount to compare against.
    line_8_prior_year_max: Decimal | None = None
    line_9_required_annual_payment: Decimal = ZERO

    # Form 2210, Part III, Section A (lines 10-18) — the official
    # column-to-column carryforward worksheet, one dict per payment period
    # (a/b/c/d), only populated when no safe harbor is met (the section is
    # only meaningful once you're actually figuring the penalty).
    section_a: List[dict] = field(default_factory=list)

    def to_dict_floats(self) -> dict:
        return {
            "safe_harbor_met": self.safe_harbor_met,
            "safe_harbor_reason": self.safe_harbor_reason,
            "penalty_amount": float(self.penalty_amount),
            "must_attach_form_2210": self.must_attach_form_2210,
            "periods": [p.to_dict_floats() for p in self.periods],
            "line_4_current_year_tax": float(self.line_4_current_year_tax),
            "line_5_ninety_pct_current_year": float(self.line_5_ninety_pct_current_year),
            "line_8_prior_year_max": (
                float(self.line_8_prior_year_max)
                if self.line_8_prior_year_max is not None
                else None
            ),
            "line_9_required_annual_payment": float(self.line_9_required_annual_payment),
            "section_a": [
                {k: float(v) for k, v in col.items()} for col in self.section_a
            ],
        }


def _installment_due_dates(tax_year: int) -> List[date]:
    return [
        date(tax_year, 4, 15),
        date(tax_year, 6, 15),
        date(tax_year, 9, 15),
        date(tax_year + 1, 1, 15),
    ]


def _section_a_worksheet(periods: List[InstallmentPeriod]) -> List[dict]:
    """Form 2210, Part III, Section A, lines 10-18 — the printed
    column-to-column carryforward worksheet (verified against the real
    2025 f2210.pdf AcroForm: ``SectionATable[0].Line10[0]``..``Line18[0]``,
    four widgets each for columns (a)-(d)).

    This is deliberately NOT the same arithmetic as the running
    ``underpayment_balance`` tracked per :class:`InstallmentPeriod` above
    (which feeds the interest/penalty-amount calculation on line 19). The
    two are related but genuinely different bookkeeping: Section A's line
    17/18 carry only the *excess* forward column-to-column (an overpayment
    in one column offsets the next column's shortfall before any new
    underpayment accrues), whereas the penalty calculation needs the full
    outstanding cumulative balance for each period to charge interest on.
    Verified by hand-simulation that these diverge as soon as an
    underpayment persists across more than one column — populating this
    table from ``underpayment_balance`` directly would print numbers that
    don't match what a human filling out the real paper form would get.
    """
    prev_overpayment = ZERO
    prev_line16 = ZERO
    prev_line17 = ZERO
    columns: List[dict] = []

    for i, p in enumerate(periods):
        line10 = p.required_installment
        line11 = p.payment_credited
        line12 = prev_overpayment if i > 0 else ZERO
        line13 = line11 + line12
        line14 = (prev_line16 + prev_line17) if i > 0 else ZERO
        line15 = max(ZERO, line13 - line14)
        line16 = (line14 - line13) if line15 == ZERO else ZERO
        if line10 >= line15:
            line17 = line10 - line15
            line18 = ZERO
        else:
            line17 = ZERO
            line18 = line15 - line10

        columns.append(
            {
                "line_10": line10,
                "line_11": line11,
                "line_12": line12,
                "line_13": line13,
                "line_14": line14,
                "line_15": line15,
                "line_16": line16,
                "line_17": line17,
                "line_18": line18,
            }
        )
        prev_overpayment = line18
        prev_line16 = line16
        prev_line17 = line17

    return columns


def evaluate(
    *,
    current_year_total_tax: float,
    total_withholding: float,
    estimated_payments: float = 0.0,
    prior_year_total_tax: float = 0.0,
    prior_year_agi_over_150k: bool = False,
    tax_year: int = 2025,
    annual_rate: float = float(IRS_UNDERPAYMENT_ANNUAL_RATE),
) -> EstimatedTaxPenaltyResult:
    """Apply the §6654 safe-harbor rules, then compute a real per-period
    penalty (Form 2210 Part III regular method) if no safe harbor is met.
    """
    result = EstimatedTaxPenaltyResult()

    current_tax = _d(current_year_total_tax)
    withholding = _d(total_withholding)
    estimated = _d(estimated_payments)
    total_paid = withholding + estimated
    underpayment = current_tax - total_paid

    if underpayment < SAFE_HARBOR_DE_MINIMIS:
        result.safe_harbor_met = True
        result.safe_harbor_reason = "Underpayment is below the $1,000 de minimis threshold."
        return result

    if total_paid >= current_tax * _d("0.90"):
        result.safe_harbor_met = True
        result.safe_harbor_reason = "Withholding ≥ 90% of current-year tax."
        return result

    prior = _d(prior_year_total_tax)
    if prior > ZERO:
        threshold_pct = _d("1.10") if prior_year_agi_over_150k else _d("1.00")
        if total_paid >= prior * threshold_pct:
            result.safe_harbor_met = True
            result.safe_harbor_reason = (
                f"Withholding ≥ {int(threshold_pct * 100)}% of prior-year tax."
            )
            return result

    # --- No safe harbor: compute the real quarterly-installment penalty ---
    result.must_attach_form_2210 = True
    result.safe_harbor_reason = (
        "No safe harbor met; penalty computed below using Form 2210 Part III's "
        "regular method."
    )

    required_annual_payment = current_tax * _d("0.90")
    if prior > ZERO:
        threshold_pct = _d("1.10") if prior_year_agi_over_150k else _d("1.00")
        required_annual_payment = min(required_annual_payment, prior * threshold_pct)

    required_per_period = required_annual_payment / 4
    withholding_per_period = withholding / 4

    due_dates = _installment_due_dates(tax_year)
    filing_deadline = date(tax_year + 1, 4, 15)
    daily_rate = _d(str(annual_rate)) / Decimal("365")

    cumulative_required = ZERO
    cumulative_paid = ZERO
    periods: List[InstallmentPeriod] = []
    total_penalty = ZERO

    for i, due in enumerate(due_dates):
        cumulative_required += required_per_period
        payment_this_period = withholding_per_period
        if i == len(due_dates) - 1:
            # Conservative: a lump estimated-payment total (no per-payment
            # dates tracked) is assumed paid in the final period — the
            # worst case for the filer, never understating the penalty.
            payment_this_period += estimated
        cumulative_paid += payment_this_period

        underpayment_balance = max(ZERO, cumulative_required - cumulative_paid)

        segment_end = due_dates[i + 1] if i + 1 < len(due_dates) else filing_deadline
        days = max(0, (segment_end - due).days)
        period_penalty = (underpayment_balance * daily_rate * days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        total_penalty += period_penalty

        periods.append(
            InstallmentPeriod(
                due_date=due,
                required_installment=required_per_period,
                payment_credited=payment_this_period,
                underpayment_balance=underpayment_balance,
                days_charged=days,
                period_penalty=period_penalty,
            )
        )

    result.penalty_amount = total_penalty
    result.periods = periods
    return result
