# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""ITIN eligibility — when Form W-7 must be attached.

A nonresident alien who does not have an SSN and is not eligible to obtain
one must apply for an Individual Taxpayer Identification Number (ITIN) by
attaching Form W-7 to their first US return. Renewals are required when an
ITIN has not been used on a return for three consecutive tax years.

Reference: IRS Pub 1915; Form W-7 instructions; IRC §6109(a)(3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

WHY_CODE = Literal[
    "a",  # NRA required to obtain ITIN to claim tax treaty benefit
    "b",  # NRA filing a US tax return
    "c",  # US resident alien (based on days) filing a US tax return
    "d",  # Dependent of a US citizen / resident
    "e",  # Spouse of a US citizen / resident
    "f",  # NRA student/professor/researcher filing a US tax return
    "g",  # Dependent / spouse of an NRA visa holder
    "h",  # Other (specify in W-7 reason field)
]


@dataclass
class ITINEligibility:
    needs_w7: bool = False
    reason_code: Optional[WHY_CODE] = None
    is_renewal: bool = False
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "needs_w7": self.needs_w7,
            "reason_code": self.reason_code,
            "is_renewal": self.is_renewal,
            "explanation": self.explanation,
        }


def evaluate(
    *,
    has_ssn: bool,
    has_existing_itin: bool,
    itin_last_used_on_return_year: Optional[int] = None,
    current_tax_year: int = 2025,
    is_student: bool = True,
    claiming_treaty_benefit: bool = False,
) -> ITINEligibility:
    """Decide whether the filer must include a Form W-7 with the return.

    Args:
        has_ssn: True if the filer already holds a Social Security Number.
        has_existing_itin: True if the filer was previously issued an ITIN.
        itin_last_used_on_return_year: Most recent year the existing ITIN
            appeared on a filed return. Used to detect 3-year non-use
            expiration.
        current_tax_year: Calendar year of the current return.
        is_student: True for F/J/M/Q students (drives reason code ``f``).
        claiming_treaty_benefit: True when the return claims at least one
            treaty exemption (drives reason code ``a`` when ITIN is sought
            specifically to claim that benefit).
    """
    if has_ssn:
        return ITINEligibility(
            needs_w7=False, explanation="Filer has an SSN; no ITIN application required."
        )

    if has_existing_itin and itin_last_used_on_return_year is not None:
        years_unused = current_tax_year - itin_last_used_on_return_year
        if years_unused >= 3:
            return ITINEligibility(
                needs_w7=True,
                reason_code="f" if is_student else "b",
                is_renewal=True,
                explanation=(
                    f"Existing ITIN has not been used on a return for "
                    f"{years_unused} years; renewal required per Pub 1915. "
                    f"Mail W-7 to Austin ITIN Operations."
                ),
            )
        return ITINEligibility(
            needs_w7=False,
            explanation="Existing ITIN remains active (used within the past 3 years).",
        )

    # No SSN, no existing ITIN → first-time application.
    if claiming_treaty_benefit:
        code: WHY_CODE = "a"
    elif is_student:
        code = "f"
    else:
        code = "b"
    return ITINEligibility(
        needs_w7=True,
        reason_code=code,
        is_renewal=False,
        explanation=(
            "Filer has no SSN or existing ITIN; first-time Form W-7 application "
            "required. Attach W-7 to the front of the 1040-NR and mail to Austin "
            "ITIN Operations (PO Box 149342, Austin TX 73301-9342)."
        ),
    )
