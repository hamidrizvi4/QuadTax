# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Schedule A (Form 1040-NR) — NRA-eligible itemized deductions.

A nonresident alien filing Form 1040-NR may itemize on Schedule A but the
catalog of allowable deductions is far narrower than for citizens:

    * State and local income tax actually withheld (line 1a) — capped at
      $10,000 in total state-and-local-tax (SALT) per IRC §164(b)(6).
    * Gifts to US 501(c)(3) charities (line 2/3/4).
    * Casualty and theft losses attributable to a federally declared
      disaster (line 6).
    * "Other" itemized — narrow set; most miscellaneous deductions were
      eliminated by TCJA (2018+).

Explicitly DISALLOWED on 1040-NR Schedule A:
    * Home mortgage interest
    * Real estate / property tax
    * Foreign income tax (foreign tax credit instead, via Form 1116)
    * Medical expenses
    * Job expenses (subject to 2% floor, eliminated by TCJA anyway)

Source: 2024 Form 1040-NR Schedule A instructions; Pub 519 Ch 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

ZERO = Decimal("0")
SALT_CAP = Decimal("10000")


def _d(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass
class SchAResult:
    """Per-line totals after applying the SALT cap and disallowance rules."""

    state_local_income_tax: Decimal = ZERO
    salt_cap_bite: Decimal = ZERO          # Amount disallowed by the $10k cap
    charitable_cash: Decimal = ZERO
    charitable_noncash: Decimal = ZERO
    casualty_disaster_loss: Decimal = ZERO
    other_itemized: Decimal = ZERO
    total: Decimal = ZERO
    disallowed_items: list[str] = field(default_factory=list)

    def to_dict_floats(self) -> dict:
        return {
            "state_local_income_tax": float(self.state_local_income_tax),
            "salt_cap_bite": float(self.salt_cap_bite),
            "charitable_cash": float(self.charitable_cash),
            "charitable_noncash": float(self.charitable_noncash),
            "casualty_disaster_loss": float(self.casualty_disaster_loss),
            "other_itemized": float(self.other_itemized),
            "total": float(self.total),
            "disallowed_items": list(self.disallowed_items),
        }


def compute_sch_a_nra(
    *,
    state_income_tax_withheld: float = 0.0,
    local_income_tax_withheld: float = 0.0,
    charitable_cash: float = 0.0,
    charitable_noncash: float = 0.0,
    casualty_disaster_loss: float = 0.0,
    other_itemized_allowed: float = 0.0,
    mortgage_interest_attempted: float = 0.0,
    property_tax_attempted: float = 0.0,
    foreign_income_tax_attempted: float = 0.0,
    medical_expenses_attempted: float = 0.0,
) -> SchAResult:
    """Compute the NRA Schedule A total and surface explicitly disallowed items.

    Args:
        state_income_tax_withheld: W-2 box 17 total (NY in our scope).
        local_income_tax_withheld: W-2 box 19 total (NYC/Yonkers).
        charitable_cash: Cash gifts to qualifying US 501(c)(3) organizations.
        charitable_noncash: Non-cash gifts to qualifying US 501(c)(3) organizations.
        casualty_disaster_loss: Net casualty loss in a federally declared
            disaster area.
        other_itemized_allowed: Narrow "other itemized" line (rare).
        mortgage_interest_attempted: Reported only so the result can flag it as
            disallowed; the value is NOT added into the total.
        property_tax_attempted: Same as above.
        foreign_income_tax_attempted: Same as above — channel to FTC, not Sch A.
        medical_expenses_attempted: Same as above.
    """
    result = SchAResult()

    # Apply the $10k SALT cap to state+local income tax.
    state_local = _d(state_income_tax_withheld) + _d(local_income_tax_withheld)
    if state_local > SALT_CAP:
        result.state_local_income_tax = SALT_CAP
        result.salt_cap_bite = state_local - SALT_CAP
    else:
        result.state_local_income_tax = state_local
        result.salt_cap_bite = ZERO

    result.charitable_cash = _d(charitable_cash)
    result.charitable_noncash = _d(charitable_noncash)
    result.casualty_disaster_loss = _d(casualty_disaster_loss)
    result.other_itemized = _d(other_itemized_allowed)

    result.total = (
        result.state_local_income_tax
        + result.charitable_cash
        + result.charitable_noncash
        + result.casualty_disaster_loss
        + result.other_itemized
    )

    # Surface disallowed categories so the audit log / UI can warn the user.
    if mortgage_interest_attempted and _d(mortgage_interest_attempted) > 0:
        result.disallowed_items.append(
            f"Mortgage interest (${float(mortgage_interest_attempted):,.0f}) is not "
            "deductible on Form 1040-NR Schedule A."
        )
    if property_tax_attempted and _d(property_tax_attempted) > 0:
        result.disallowed_items.append(
            f"Real-estate / property tax (${float(property_tax_attempted):,.0f}) is "
            "not deductible on Form 1040-NR Schedule A."
        )
    if foreign_income_tax_attempted and _d(foreign_income_tax_attempted) > 0:
        result.disallowed_items.append(
            f"Foreign income tax (${float(foreign_income_tax_attempted):,.0f}) is not "
            "deductible on Schedule A; claim as Foreign Tax Credit on Form 1116."
        )
    if medical_expenses_attempted and _d(medical_expenses_attempted) > 0:
        result.disallowed_items.append(
            f"Medical expenses (${float(medical_expenses_attempted):,.0f}) are not "
            "deductible on Form 1040-NR Schedule A."
        )

    return result


def choose_deduction(
    *,
    itemized_total: float,
    standard_deduction_available: float,
) -> tuple[float, str]:
    """Pick the larger of itemized vs. (NRA-restricted) standard deduction.

    Args:
        itemized_total: Schedule A total from :func:`compute_sch_a_nra`.
        standard_deduction_available: The NRA's standard deduction (typically
            $0; $15,000 single under India Article 21(2)).

    Returns:
        Tuple of ``(chosen_amount, label)``; ``label`` is ``"itemized"`` or
        ``"standard"``.
    """
    itemized = _d(itemized_total)
    standard = _d(standard_deduction_available)
    if itemized >= standard:
        return float(itemized), "itemized"
    return float(standard), "standard"
