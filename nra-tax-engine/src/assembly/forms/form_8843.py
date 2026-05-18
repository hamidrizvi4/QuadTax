"""Form 8843 — Statement for Exempt Individuals and Individuals with a Medical Condition.

Required every tax year for every F-1 / J-1 / M-1 / Q-1 holder regardless
of income (and even without filing a 1040-NR). Five parts:

    Part I    Personal information (always required)
    Part II   J-1 teachers/trainees (filled only for J-1 teacher/researcher)
    Part III  F/J/M/Q students (filled for student visa holders)
    Part IV   Professional athletes (not applicable to students)
    Part V    Medical exception (only when invoked)
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

    return {
        # Part I — always populated
        "part_I_name": f"{ident.first_name} {ident.last_name}".strip(),
        "part_I_us_tin": ident.primary_tin,
        "part_I_address_us_line1": ident.us_address_line1,
        "part_I_address_us_city_state_zip": (
            f"{ident.us_city}, {ident.us_state} {ident.us_zip}".strip(", ").strip()
        ),
        "part_I_address_foreign_line1": ident.foreign_address_line1,
        "part_I_address_foreign_country": ident.foreign_country,
        "part_I_visa_type_current": visa,
        "part_I_country_citizenship": ident.country_of_citizenship,
        "part_I_passport_number": ident.passport_number,
        "part_I_passport_issuing_country": ident.passport_country,
        "part_I_days_current_year": residency.spt_days_current_year,
        # Part II — teachers/trainees (J-1 researcher subtype). Blank for student.
        "part_II_relevant": visa == "J-1",  # may need refinement for student subtype
        # Part III — students
        "part_III_relevant": is_student_visa,
        "part_III_line_9_school_name": "",  # intake-derived
        "part_III_line_10_director_name": "",  # intake-derived
        "part_III_line_11_years_in_exempt_status": residency.years_in_exempt_status,
        "part_III_line_12_intend_to_remain_us": False,  # intake-derived
        "part_III_line_13_taken_steps_to_remain": False,  # intake-derived
        "part_III_line_14_substantially_complied": True,  # intake-derived
        # Part IV — professional athletes (n/a for students)
        "part_IV_relevant": False,
        # Part V — medical exception (only when invoked)
        "part_V_relevant": False,
        # Signature
        "signature_date": "",  # filled at filing time
    }
