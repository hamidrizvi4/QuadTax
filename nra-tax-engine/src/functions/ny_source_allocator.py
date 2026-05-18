# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""NY-source income allocation for nonresident filers.

NY nonresidents are taxed only on NY-source income (NY Tax Law §631).
For wages from an employer located in NY, the standard apportionment is:

    NY-source wages = total wages × (NY work days / total work days)

For 1042-S income from a NY-located educational institution (the
typical F-1 scenario), the income is 100% NY-source.

For W-2 wages from an employer outside NY, the income is 0% NY-source
unless the filer physically worked in NY (rare for students).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NYSourceAllocation:
    total_wages: float = 0.0
    ny_source_wages: float = 0.0
    non_ny_source_wages: float = 0.0
    ny_work_days: int = 0
    total_work_days: int = 0
    ny_source_pct: float = 0.0
    ny_source_1042s_gross: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_wages": self.total_wages,
            "ny_source_wages": self.ny_source_wages,
            "non_ny_source_wages": self.non_ny_source_wages,
            "ny_work_days": self.ny_work_days,
            "total_work_days": self.total_work_days,
            "ny_source_pct": self.ny_source_pct,
            "ny_source_1042s_gross": self.ny_source_1042s_gross,
        }


def allocate(
    *,
    total_w2_wages: float,
    ny_work_days: int,
    total_work_days: int,
    employer_in_ny: bool = True,
    total_1042s_gross: float = 0.0,
    institution_1042s_in_ny: bool = True,
) -> NYSourceAllocation:
    """Apportion W-2 wages by NY work days and route 1042-S by institution location.

    Args:
        total_w2_wages: Aggregate W-2 box 1 wages.
        ny_work_days: Days the filer physically worked in NY.
        total_work_days: Total days the filer worked anywhere.
        employer_in_ny: True if the W-2 employer is based in NY (drives the
            apportionment formula).
        total_1042s_gross: Aggregate 1042-S gross (typically the university
            scholarship/wages).
        institution_1042s_in_ny: True if the 1042-S issuer is a NY institution
            (the dominant case for NY-state-school F-1 students).
    """
    result = NYSourceAllocation(
        total_wages=total_w2_wages,
        ny_work_days=ny_work_days,
        total_work_days=total_work_days,
    )

    # W-2 apportionment.
    if employer_in_ny and total_work_days > 0:
        pct = max(0.0, min(1.0, ny_work_days / total_work_days))
        result.ny_source_pct = pct
        result.ny_source_wages = round(total_w2_wages * pct, 2)
    elif employer_in_ny and total_work_days == 0:
        # No work-day data — default to 100% NY-source (conservative for student
        # at a NY-located employer who didn't track days).
        result.ny_source_pct = 1.0
        result.ny_source_wages = total_w2_wages
    else:
        # Employer outside NY → no NY-source wages.
        result.ny_source_pct = 0.0
        result.ny_source_wages = 0.0

    result.non_ny_source_wages = max(0.0, total_w2_wages - result.ny_source_wages)

    # 1042-S routing.
    if institution_1042s_in_ny:
        result.ny_source_1042s_gross = total_1042s_gross
    else:
        result.ny_source_1042s_gross = 0.0

    return result
