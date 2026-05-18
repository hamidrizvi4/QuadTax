# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""NY residency determination — separate from federal SPT.

New York runs its own residency test under NY Tax Law §605:

    1. **Domicile in NY** → NY resident (rare for F-1 students).
    2. **Statutory residency** → not domiciled, but maintains a *permanent
       place of abode* in NY for more than 11 months AND is physically
       present in NY more than 183 days. The Knight case excludes
       university dormitories from the permanent-place-of-abode prong.
    3. **Part-year** when the filer moved into or out of NY during the year.
    4. **Nonresident** otherwise — the default for most F-1 students.

NY does NOT honor federal tax treaties (NY Pub 88, IT-203-I instructions).
Treaty-exempt income at the federal level is added back to NY taxable income.

References:
    * NY Tax Law §605
    * 20 NYCRR 105.20
    * Matter of Petition of Knight (NY DTA 2002) — student dorm exclusion
    * NY Publication 88 — Federal Modifications
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

NYStatus = Literal["resident", "part_year", "nonresident"]


@dataclass
class NYResidencyResult:
    status: NYStatus = "nonresident"
    reason: str = ""
    days_in_ny: int = 0
    has_permanent_abode: bool = False
    is_student_dorm: bool = False
    domiciled_in_ny: bool = False
    abode_months_in_year: int = 0
    nyc_resident: bool = False
    yonkers_resident: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "days_in_ny": self.days_in_ny,
            "has_permanent_abode": self.has_permanent_abode,
            "is_student_dorm": self.is_student_dorm,
            "domiciled_in_ny": self.domiciled_in_ny,
            "abode_months_in_year": self.abode_months_in_year,
            "nyc_resident": self.nyc_resident,
            "yonkers_resident": self.yonkers_resident,
        }


def evaluate(
    *,
    days_in_ny: int,
    has_permanent_abode_in_ny: bool,
    abode_months_in_year: int,
    is_student_dorm: bool,
    domiciled_in_ny: bool,
    moved_into_ny_mid_year: bool = False,
    moved_out_of_ny_mid_year: bool = False,
    nyc_address: bool = False,
    yonkers_address: bool = False,
) -> NYResidencyResult:
    """Classify the filer for NY tax purposes.

    Args:
        days_in_ny: Calendar days the filer was physically present anywhere in NY.
        has_permanent_abode_in_ny: True if filer maintained a NY abode (rented or owned).
        abode_months_in_year: Months the abode was maintained (1-12).
        is_student_dorm: True if the only NY abode is a university dormitory; the
            Knight case excludes this from "permanent place of abode."
        domiciled_in_ny: True if NY is the filer's permanent home/center of life.
        moved_into_ny_mid_year: True for arrival-year part-year resident.
        moved_out_of_ny_mid_year: True for departure-year part-year resident.
        nyc_address: True if the NY abode is within NYC (drives NYC residency).
        yonkers_address: True if the NY abode is within Yonkers.
    """
    result = NYResidencyResult(
        days_in_ny=days_in_ny,
        has_permanent_abode=has_permanent_abode_in_ny,
        is_student_dorm=is_student_dorm,
        domiciled_in_ny=domiciled_in_ny,
        abode_months_in_year=abode_months_in_year,
        nyc_resident=False,
        yonkers_resident=False,
    )

    # 1) Domicile prong.
    if domiciled_in_ny:
        result.status = "resident"
        result.reason = "Domiciled in New York under NY Tax Law §605(b)(1)(A)."
        result.nyc_resident = nyc_address
        result.yonkers_resident = yonkers_address
        return result

    # 2) Part-year flag.
    if moved_into_ny_mid_year or moved_out_of_ny_mid_year:
        result.status = "part_year"
        result.reason = (
            "Part-year resident: filer moved into or out of NY during the tax year."
        )
        result.nyc_resident = nyc_address
        result.yonkers_resident = yonkers_address
        return result

    # 3) Statutory residency prong (NY Tax Law §605(b)(1)(B)).
    #    Permanent place of abode > 11 months AND > 183 days in NY.
    #    Student dormitories are excluded (Knight, NY DTA 2002).
    effective_abode = has_permanent_abode_in_ny and not is_student_dorm
    if (
        effective_abode
        and abode_months_in_year > 11
        and days_in_ny > 183
    ):
        result.status = "resident"
        result.reason = (
            "Statutory resident: permanent abode > 11 months and > 183 days in NY "
            "(NY Tax Law §605(b)(1)(B)). Student dorms excluded under Knight."
        )
        result.nyc_resident = nyc_address
        result.yonkers_resident = yonkers_address
        return result

    # 4) Nonresident default.
    result.status = "nonresident"
    if is_student_dorm:
        result.reason = (
            "Nonresident: only NY abode is a university dormitory, which under "
            "Matter of Petition of Knight is NOT a permanent place of abode."
        )
    elif not has_permanent_abode_in_ny:
        result.reason = "Nonresident: no permanent place of abode in NY."
    elif abode_months_in_year <= 11:
        result.reason = (
            "Nonresident: abode held ≤ 11 months — fails the statutory-residency "
            "duration prong."
        )
    elif days_in_ny <= 183:
        result.reason = (
            "Nonresident: ≤ 183 days physically present in NY — fails the day-count prong."
        )
    else:
        result.reason = "Nonresident."

    # NYC/Yonkers residency only applies if domiciled there OR statutory NY resident
    # is in the NYC five-boroughs; for nonresidents both are False.
    result.nyc_resident = False
    result.yonkers_resident = False
    return result
