"""Form 8843 — Statement for Exempt Individuals and Individuals with a Medical
Condition.

Required every tax year for every F-1 / J-1 / M-1 / Q-1 holder regardless
of income (and even without filing a 1040-NR).

Real AcroForm field layout (dumped from assets/templates/2025/f8843.pdf via
raw widget annotations — /AP/N export states, not reader.get_fields()'s
/_States_ summary — and cross-referenced against the printed line text via
position-sorted extract_text; do NOT trust field-name-number ordering
assumptions, verify against the actual rects):

    Page 1 — Part I  General Information (all filers)
        f1_01/f1_02/f1_03   fiscal-year begin/end dates (non-calendar-year
                             filers only — this engine only supports
                             calendar-year filers, so always blank)
        f1_04               Line "Your first name and initial"
        f1_05               Line "Last name"
        f1_06               Line "Your U.S. taxpayer identification number"
        f1_07               "Address in country of residence" (foreign)
        f1_08               "Address in the United States"
        f1_09               Line 1a — type of U.S. visa AND date entered US
        f1_10               Line 1b — current nonimmigrant status
        f1_11               Line 2  — country/countries of citizenship
        f1_12               Line 3a — country/countries that issued passport
        f1_13               Line 3b — passport number(s)
        f1_14/f1_15/f1_16   Line 4a — days present: tax_year/-1/-2
        f1_17               Line 4b — days excluded from SPT
    Page 1 — Part II  Teachers and Trainees (J-1 teacher_researcher/trainee)
        f1_18               Line 5 — teaching institution (name/addr/phone)
        f1_19               Line 6 — trainee program director (name/addr/phone)
        f1_20..f1_25        Line 7 — visa type (J or Q) held during each of
                             the 6 calendar years before tax_year, oldest to
                             newest
        c1_1[0]/c1_1[1]     Line 8 — "exempt >= 2 of preceding 6 years?"
                             Yes/No — TWO INDEPENDENT /Btn fields (states
                             ['/1','/Off'] and ['/2','/Off']), not a shared
                             radio group
    Page 1 — Part III  Students (F-1/M-1/Q-1, or J-1 student subtype)
        f1_26               Line 9  — academic institution attended
        f1_27               Line 10 — program director (name/addr/phone)
        f1_28..f1_33        Line 11 — visa type (F, J, M, or Q) held during
                             each of the 6 calendar years before tax_year
        c1_2[0]/c1_2[1]     Line 12 — "exempt for part of >5 cal. years?"
                             Yes/No, same two-independent-fields pattern
        c1_3[0]/c1_3[1]     Line 13 — "applied for LPR status?" Yes/No, same
                             pattern
        f1_34               Line 14 — explanation if line 13 is "Yes"
    Page 2 — Part IV  Professional Athletes (f2_01, f2_02) and
             Part V   Individuals With a Medical Condition (f2_03..f2_08)
        Out of scope for this engine: no intake path collects charitable
        sports-event data or medical-condition/physician data anywhere in
        ReturnStateObject, so these two parts are never populated. Left
        unmapped entirely (no f2_01..f2_08 entries in f8843_fields.json)
        rather than fabricated.

Two fields with no backing intake/state data — left blank rather than
fabricated, see inline comments: Part II line 5/6 (teaching institution /
program director) and Part III line 9/10 (academic institution / program
director). Nothing in ReturnStateObject captures a school or program-
sponsor name; ``IncomeState.employer_name`` is the *wage payer* for FICA
Form 843/8316 purposes, not the academic institution, and would frequently
be wrong (e.g. an on-campus job at a different school than the one that
issued the visa, or a scholarship-only filer with no employer at all).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from src.assembly.forms.form_8833 import _format_address

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def _fmt_mmddyyyy(iso_date) -> str:
    """Convert an ISO ``YYYY-MM-DD`` date to ``MM/DD/YYYY``.

    f1_09 is a plain (non-comb) text field, so slashes are safe here
    (contrast form_w7.py's ``_fmt_comb_date``, which strips them because
    that PDF's date fields are fixed 8-cell comb fields).
    """
    if not iso_date:
        return ""
    try:
        y, m, d = str(iso_date).split("-")
        return f"{m}/{d}/{y}"
    except ValueError:
        return ""


def _yes_no(value: bool, applicable: bool) -> Tuple[bool, bool]:
    """Return ``(yes_checked, no_checked)`` for a paired Yes/No line.

    The real PDF encodes each Yes/No line as two INDEPENDENT /Btn fields
    (e.g. c1_2[0] states ``['/1', '/Off']`` for Yes, c1_2[1] states
    ``['/2', '/Off']`` for No) rather than one shared radio group — verified
    via the widget /AP/N export states, not reader.get_fields()'s /_States_
    summary. Passing bare bools for BOTH kids (matching the
    ``schedule_oi.py`` c1_6/c1_7/... and ``form_1040nr.py``
    ``digital_assets_yes``/``digital_assets_no`` convention already used
    elsewhere in this codebase for the identical PDF quirk) lets
    FormPopulator._format_for_acro resolve each kid against its OWN real
    ``/_States_`` — safe here because each kid's states are genuinely just
    its one "on" state plus "/Off", not two different "on" meanings sharing
    one fallback. Previously form_8843.py only mapped the "Yes" kid and
    passed a raw bool through, which meant a computed ``False`` correctly
    left "Yes" unchecked but never checked "No" either — both boxes stayed
    blank, which reads as "left unanswered" rather than "No" on the actual
    filled PDF. When the line isn't applicable to this filer at all (e.g.
    Part III's lines 12/13 for a Part II teacher), both boxes stay
    unchecked rather than guessing an answer for a question the filer was
    never asked.
    """
    if not applicable:
        return False, False
    return bool(value), not bool(value)


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    residency = state.residency

    visa = (residency.exempt_visa_type or "").upper()
    subtype = residency.visa_subtype

    # Part II (Teachers and Trainees, lines 5-8) vs Part III (Students,
    # lines 9-14) routing. Verified against the real AcroForm text: Part II
    # line 7's 6-year grid asks for "type of U.S. visa (J or Q)"; Part III
    # line 11's grid asks for "type of U.S. visa (F, J, M, or Q)". A J-1
    # filer can land in EITHER part depending on their role.
    # ResidencyState.visa_subtype (seeded by intake/MCQRouter, and already
    # consumed by SubstantialPresenceCalculator's 2-year-vs-5-year exempt
    # window logic) is the only signal available to distinguish them, so it
    # drives routing here too — the previous version ignored visa_subtype
    # entirely and routed every J-1 to Part III by default, which silently
    # dropped Part II altogether for J-1 teachers/researchers/trainees.
    is_teacher = visa == "J-1" and subtype == "teacher_researcher"
    is_trainee = visa == "J-1" and subtype == "trainee"
    is_part_ii = is_teacher or is_trainee
    # F-1/M-1/Q-1 are always students in this engine's scope (visa_subtype
    # is documented as "only meaningful for J-1"). A J-1 filer with
    # subtype "student" is a Part III student. A J-1 filer with subtype
    # "other" doesn't map cleanly to either IRS category under our intake's
    # 4-way taxonomy (real-world J categories like "short-term scholar" or
    # "specialist" exist that intake doesn't distinguish from "student")
    # — falls back to Part III as the more common/conservative case rather
    # than silently filing neither part.
    is_part_iii = not is_part_ii and visa in {"F-1", "J-1", "M-1", "Q-1"}

    us_address = _format_address(
        ident.us_address_line1,
        ident.us_address_line2,
        ident.us_city,
        ident.us_state,
        ident.us_zip,
        "",
    )
    foreign_address = _format_address(
        ident.foreign_address_line1,
        ident.foreign_address_line2,
        ident.foreign_city,
        ident.foreign_state_province,
        ident.foreign_postal_code,
        ident.foreign_country,
    )

    # Line 1a wants the visa type AND the date the filer entered the US.
    # ResidencyState.first_us_entry_date carries the latter (intake-seeded,
    # also used by L1's arrival-year dual-status detection).
    entry_date = _fmt_mmddyyyy(residency.first_us_entry_date)
    if visa and entry_date:
        line_1a = f"{visa}, entered {entry_date}"
    else:
        line_1a = visa or ""

    # Line 4b — days excluded from the SPT because of exempt status. Only
    # meaningful when the filer actually claimed the exemption; raw presence
    # minus SPT-counted presence gives the excluded count.
    days_excluded = max(
        0, residency.days_present_current_year - residency.spt_days_current_year
    )

    # Line 7 (Part II) / Line 11 (Part III) — visa type held during each of
    # the 6 calendar years immediately before the current tax year (always a
    # rolling window, e.g. 2019-2024 for TY2025 — never hardcode literal
    # years here).
    first_exempt_year = (
        state.tax_year - residency.years_in_exempt_status + 1
        if residency.years_in_exempt_status > 0
        else state.tax_year
    )
    grid_years = list(range(state.tax_year - 6, state.tax_year))
    grid_relevant = is_part_ii or is_part_iii
    visa_by_year = {
        year: (visa if grid_relevant and year >= first_exempt_year else "")
        for year in grid_years
    }

    # Line 8 (Part II) — "Were you exempt as a teacher, trainee, or student
    # for any part of 2 of the preceding 6 calendar years?" Mirrors line
    # 12's "> 5" pattern but with the 2-calendar-year J-1 teacher/researcher
    # window (IRC §7701(b)(5)(E)) instead of the 5-year student window; both
    # rely on the same continuous-presence approximation already documented
    # on ResidencyState.years_in_exempt_status / SubstantialPresenceCalculator.
    exempt_2_of_6_yes, exempt_2_of_6_no = _yes_no(
        residency.years_in_exempt_status > 2, is_part_ii
    )
    # Line 12 (Part III) — "Were you exempt ... for any part of more than 5
    # calendar years?"
    exempt_more_than_5_years_yes, exempt_more_than_5_years_no = _yes_no(
        residency.years_in_exempt_status > 5, is_part_iii
    )
    # Line 13 (Part III) — "did you apply for, or take other affirmative
    # steps toward, LPR status?" No intake field collects LPR (green card)
    # application steps today — False is the correct default for the
    # overwhelming majority of student filers, but this should become
    # intake-derived once that's collected.
    applied_for_lpr_status = False
    applied_for_lpr_yes, applied_for_lpr_no = _yes_no(
        applied_for_lpr_status, is_part_iii
    )

    return {
        # ---- Part I — always populated -------------------------------
        "part_I_first_name": f"{ident.first_name} {ident.middle_initial}".strip(),
        "part_I_last_name": ident.last_name,
        "part_I_us_tin": ident.primary_tin,
        "part_I_address_us_line1": us_address,
        "part_I_address_foreign_line1": foreign_address,
        "part_I_line_1a_visa_and_entry_date": line_1a,
        "part_I_line_1b_current_status": visa,
        "part_I_country_citizenship": ident.country_of_citizenship,
        "part_I_passport_issuing_country": ident.passport_country,
        "part_I_passport_number": ident.passport_number,
        # Line 4a — raw physical presence, NOT the SPT-adjusted count (which
        # is 0 for a fully-exempt filer and would misreport actual presence).
        "part_I_days_current_year": residency.days_present_current_year,
        "part_I_days_year_minus_1": residency.days_present_year_minus_1,
        "part_I_days_year_minus_2": residency.days_present_year_minus_2,
        "part_I_days_excluded_for_spt": days_excluded,
        # ---- Part II — Teachers and Trainees ---------------------------
        "_part_II_relevant": is_part_ii,
        "_part_II_role": "teacher" if is_teacher else ("trainee" if is_trainee else ""),
        "part_II_line_5_teaching_institution": "",  # intake-derived; see module docstring
        "part_II_line_6_program_director": "",  # intake-derived; see module docstring
        "part_II_line_7_visa_yr_minus_6": visa_by_year[grid_years[0]] if is_part_ii else "",
        "part_II_line_7_visa_yr_minus_5": visa_by_year[grid_years[1]] if is_part_ii else "",
        "part_II_line_7_visa_yr_minus_4": visa_by_year[grid_years[2]] if is_part_ii else "",
        "part_II_line_7_visa_yr_minus_3": visa_by_year[grid_years[3]] if is_part_ii else "",
        "part_II_line_7_visa_yr_minus_2": visa_by_year[grid_years[4]] if is_part_ii else "",
        "part_II_line_7_visa_yr_minus_1": visa_by_year[grid_years[5]] if is_part_ii else "",
        "part_II_line_8_exempt_2_of_6_yes": exempt_2_of_6_yes,
        "part_II_line_8_exempt_2_of_6_no": exempt_2_of_6_no,
        # ---- Part III — Students ---------------------------------------
        "_part_III_relevant": is_part_iii,
        "part_III_line_9_school_name": "",  # intake-derived; see module docstring
        "part_III_line_10_director_name": "",  # intake-derived; see module docstring
        # Oldest (tax_year - 6) to newest (tax_year - 1).
        "part_III_line_11_visa_yr_minus_6": visa_by_year[grid_years[0]] if is_part_iii else "",
        "part_III_line_11_visa_yr_minus_5": visa_by_year[grid_years[1]] if is_part_iii else "",
        "part_III_line_11_visa_yr_minus_4": visa_by_year[grid_years[2]] if is_part_iii else "",
        "part_III_line_11_visa_yr_minus_3": visa_by_year[grid_years[3]] if is_part_iii else "",
        "part_III_line_11_visa_yr_minus_2": visa_by_year[grid_years[4]] if is_part_iii else "",
        "part_III_line_11_visa_yr_minus_1": visa_by_year[grid_years[5]] if is_part_iii else "",
        "part_III_line_12_exempt_more_than_5_years_yes": exempt_more_than_5_years_yes,
        "part_III_line_12_exempt_more_than_5_years_no": exempt_more_than_5_years_no,
        "part_III_line_13_applied_for_lpr_status_yes": applied_for_lpr_yes,
        "part_III_line_13_applied_for_lpr_status_no": applied_for_lpr_no,
        # Line 14 — explanation, only meaningful when line 13 is Yes.
        "part_III_line_14_explanation": "",
        # ---- Part IV — Professional Athletes (out of scope) -------------
        # No intake path collects charitable sports-event / EIN data
        # anywhere in ReturnStateObject. f2_01/f2_02 intentionally left out
        # of f8843_fields.json entirely rather than mapped-but-blank.
        "_part_IV_relevant": False,
        # ---- Part V — Medical Condition exception (out of scope) --------
        # No intake path collects medical-condition / physician-statement
        # data anywhere in ReturnStateObject. f2_03..f2_08 intentionally
        # left out of f8843_fields.json entirely rather than mapped-but-blank.
        "_part_V_relevant": False,
    }
