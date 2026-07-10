"""Form 8843 — Statement for Exempt Individuals and Individuals with a Medical Condition.

Required every tax year for every F-1 / J-1 / M-1 / Q-1 holder regardless
of income (and even without filing a 1040-NR). Five parts:

    Part I    Personal information (always required)
    Part II   J-1 teachers/trainees (filled only for J-1 teacher/researcher)
    Part III  F/J/M/Q students (filled for student visa holders)
    Part IV   Professional athletes (not applicable to students)
    Part V    Medical exception (only when invoked)

The vendored 2025 PDF has no "this part applies" marker checkbox anywhere —
applicability is conveyed structurally by which lines are filled, not by a
field. The part_*_relevant keys below are therefore informational only
(underscore-prefixed so FormPopulator never tries to write them to the
PDF) — they exist for the frontend/audit trail, not the form itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    residency = state.residency

    visa = (residency.exempt_visa_type or "").upper()
    is_student_visa = visa in {"F-1", "M-1", "Q-1"} or (visa == "J-1")
    # Part II is for J-1 teachers/trainees; Part III is for F/J/M/Q students.
    # Without an explicit subtype on residency we route J-1 to Part III by default
    # (most common case) — the L1 agent should set a sub-flag for J-1 researchers
    # to populate Part II instead.

    us_address = ", ".join(
        part
        for part in (
            ident.us_address_line1,
            f"{ident.us_city}, {ident.us_state} {ident.us_zip}".strip(", ").strip(),
        )
        if part
    )
    foreign_address = ", ".join(
        part for part in (ident.foreign_address_line1, ident.foreign_country) if part
    )

    # Line 4b — days excluded from the SPT because of exempt status. Only
    # meaningful when the filer actually claimed the exemption; raw presence
    # minus SPT-counted presence gives the excluded count.
    days_excluded = max(
        0, residency.days_present_current_year - residency.spt_days_current_year
    )

    # Line 11 — visa type held during each of the 6 calendar years
    # immediately before the current tax year (always a rolling window, e.g.
    # 2019-2024 for TY2025 — never hardcode literal years here).
    first_exempt_year = (
        state.tax_year - residency.years_in_exempt_status + 1
        if residency.years_in_exempt_status > 0
        else state.tax_year
    )
    grid_years = list(range(state.tax_year - 6, state.tax_year))
    visa_by_year = {
        year: (visa if is_student_visa and year >= first_exempt_year else "")
        for year in grid_years
    }

    exempt_more_than_5_years = residency.years_in_exempt_status > 5
    # No intake field collects LPR (green card) application steps today —
    # False is the correct default for the overwhelming majority of student
    # filers, but this should become intake-derived once that's collected.
    applied_for_lpr_status = False

    return {
        # Part I — always populated
        "part_I_name": f"{ident.first_name} {ident.last_name}".strip(),
        "part_I_us_tin": ident.primary_tin,
        "part_I_address_us_line1": us_address,
        "part_I_address_foreign_line1": foreign_address,
        "part_I_visa_type_current": visa,
        "part_I_country_citizenship": ident.country_of_citizenship,
        "part_I_passport_number": ident.passport_number,
        "part_I_passport_issuing_country": ident.passport_country,
        # Line 4a — raw physical presence, NOT the SPT-adjusted count (which
        # is 0 for a fully-exempt filer and would misreport actual presence).
        "part_I_days_current_year": residency.days_present_current_year,
        "part_I_days_year_minus_1": residency.days_present_year_minus_1,
        "part_I_days_year_minus_2": residency.days_present_year_minus_2,
        # Line 4b — days excluded from the SPT count due to exempt status.
        "part_I_days_excluded_for_spt": days_excluded,
        # Part II — teachers/trainees (J-1 researcher subtype). Blank for student.
        "_part_II_relevant": visa == "J-1",  # may need refinement for student subtype
        # Part III — students
        "_part_III_relevant": is_student_visa,
        "part_III_line_9_school_name": "",  # intake-derived
        "part_III_line_10_director_name": "",  # intake-derived
        # Line 11 — visa type per year, oldest (tax_year - 6) to newest (tax_year - 1).
        "part_III_line_11_visa_yr_minus_6": visa_by_year[grid_years[0]],
        "part_III_line_11_visa_yr_minus_5": visa_by_year[grid_years[1]],
        "part_III_line_11_visa_yr_minus_4": visa_by_year[grid_years[2]],
        "part_III_line_11_visa_yr_minus_3": visa_by_year[grid_years[3]],
        "part_III_line_11_visa_yr_minus_2": visa_by_year[grid_years[4]],
        "part_III_line_11_visa_yr_minus_1": visa_by_year[grid_years[5]],
        # Line 12 — "Were you exempt ... for any part of more than 5 calendar years?"
        "part_III_line_12_exempt_more_than_5_years": exempt_more_than_5_years,
        # Line 13 — "did you apply for, or take other affirmative steps toward, LPR status?"
        "part_III_line_13_applied_for_lpr_status": applied_for_lpr_status,
        # Line 14 — explanation, only meaningful when line 13 is Yes.
        "part_III_line_14_explanation": "",
        # Part IV — professional athletes (n/a for students)
        "_part_IV_relevant": False,
        # Part V — medical exception (only when invoked)
        "_part_V_relevant": False,
    }
