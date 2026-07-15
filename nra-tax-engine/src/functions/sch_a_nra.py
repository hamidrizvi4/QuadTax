# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Schedule A (Form 1040-NR) — NRA-eligible itemized deductions.

A nonresident alien filing Form 1040-NR may itemize on Schedule A but the
catalog of allowable deductions is far narrower than for citizens:

    * State and local income tax actually withheld (line 1a) — capped at
      the SALT limitation on line 1b per IRC §164(b)(6), as amended by the
      One Big Beautiful Bill Act (OBBBA, P.L. 119-21, July 4, 2025).
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

SALT cap: the vendored TY2025 Schedule A (Form 1040-NR) PDF's own printed
line 1b text reads "Enter the smaller of line 1a or $40,000 ($20,000 if
married filing separately)" — confirmed directly against
``assets/templates/2025/f1040nra.pdf`` (a "Created 12/19/25" IRS revision).
This supersedes the pre-OBBBA $10,000 flat SALT cap (still correct for
tax years 2018-2024) that a prior version of this module hardcoded
regardless of filing status or tax year — that stale $10,000 figure was a
genuine tax-correctness bug for TY2025 returns, silently under-stating
line 1a/1b for any filer with more than $10,000 (single) / not applicable
(MFS, whose new cap of $20,000 is still above the old flat figure) of
state+local income tax withheld.

NOT implemented: OBBBA also phases the $40,000/$20,000 cap down (by 30%
of the excess over a $500,000 / $250,000-MFS MAGI threshold, floored at
$10,000) for high-income filers — see the same line 1b instructions
("If Form 1040-NR, line 11b is more than $500,000 ..., see instructions").
This function has no MAGI/line-11b input available at its call site (it's
invoked with raw withholding/gift/loss figures, not AGI), so the
phase-down is not computed here; every filer currently gets the full
$40,000/$20,000 cap regardless of income. This is a real gap for
high-income NRA filers (rare in this engine's F-1/J-1 student population)
but is NOT silently fabricated — flag for a future enhancement rather than
guessing a phase-down amount.

Source: 2025 Form 1040-NR Schedule A (vendored PDF, line 1a/1b text);
Pub 519 Ch 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

ZERO = Decimal("0")
# TY2025 (OBBBA-raised) SALT caps — see module docstring. Filing status on
# Form 1040-NR is restricted to single/MFS/QSS; QSS uses the single cap.
SALT_CAP_SINGLE = Decimal("40000")
SALT_CAP_MFS = Decimal("20000")
# Backward-compatible alias for the common (non-MFS) case.
SALT_CAP = SALT_CAP_SINGLE


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
    salt_cap_bite: Decimal = ZERO          # Amount disallowed by the SALT cap
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
    filing_status: str = "single",
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
        filing_status: 1040-NR filing status ("single", "mfs", "qss") — only
            "mfs" changes the SALT cap (to $20,000; everything else uses the
            $40,000 single/QSS cap). See module docstring for the OBBBA
            phase-down that is NOT modeled here.
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

    # Apply the TY2025 SALT cap (line 1b) to state+local income tax.
    salt_cap = SALT_CAP_MFS if filing_status == "mfs" else SALT_CAP_SINGLE
    state_local = _d(state_income_tax_withheld) + _d(local_income_tax_withheld)
    if state_local > salt_cap:
        result.state_local_income_tax = salt_cap
        result.salt_cap_bite = state_local - salt_cap
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
