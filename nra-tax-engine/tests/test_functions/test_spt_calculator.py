"""Tests for the SPT Calculator — Substantial Presence Test math."""

import pytest

from src.functions.spt_calculator import SubstantialPresenceCalculator


class TestSubstantialPresenceCalculator:
    """Test suite for the Substantial Presence Test calculator."""

    def setup_method(self):
        self.calc = SubstantialPresenceCalculator()

    def test_exempt_individual_exactly_5_years(self):
        """An F-1 student in their 5th calendar year is exempt."""
        # Arrived 2020, tax year 2024 -> 2024 - 2020 + 1 = 5. Exempt!
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="F-1",
            first_us_arrival_year=2020,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=365,
        )
        assert result["is_exempt_individual"] is True
        assert result["years_in_exempt_status"] == 5
        assert result["status"] == "nonresident_alien"

    def test_exempt_individual_6_years_spt_met(self):
        """An F-1 student in their 6th calendar year is NOT exempt, and meets SPT."""
        # Arrived 2019, tax year 2024 -> 2024 - 2019 + 1 = 6. Not exempt!
        # SPT: 365 + 365//3 + 365//6 = 365 + 121 + 60 = 546 >= 183. Resident!
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="F-1",
            first_us_arrival_year=2019,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=365,
        )
        assert result["is_exempt_individual"] is False
        assert result["years_in_exempt_status"] == 6
        assert result["status"] == "resident_alien"

    def test_spt_exactly_182_days_nonresident(self):
        """Exactly 182 days fails the SPT."""
        # Not exempt.
        # current = 122
        # minus_1 = 180 (180//3 = 60)
        # minus_2 = 0
        # Total = 122 + 60 = 182.
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="H-1B", # Non-exempt visa
            first_us_arrival_year=2020,
            days_present_current_year=122,
            days_present_minus_1=180,
            days_present_minus_2=0,
        )
        assert result["is_exempt_individual"] is False
        assert result["status"] == "nonresident_alien"

    def test_spt_exactly_183_days_resident(self):
        """Exactly 183 days passes the SPT."""
        # Not exempt.
        # current = 123
        # minus_1 = 180 (180//3 = 60)
        # minus_2 = 0 (0//6 = 0)
        # Total = 123 + 60 = 183.
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2020,
            days_present_current_year=123,
            days_present_minus_1=180,
            days_present_minus_2=0,
        )
        assert result["is_exempt_individual"] is False
        assert result["status"] == "resident_alien"

    def test_spt_fails_prong_one_30_days(self):
        """Less than 31 days in current year defaults to nonresident, even with high prior days."""
        # current = 30
        # minus_1 = 365 (365//3 = 121)
        # minus_2 = 365 (365//6 = 60)
        # Total = 30 + 121 + 60 = 211 >= 183. BUT current < 31!
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2020,
            days_present_current_year=30,
            days_present_minus_1=365,
            days_present_minus_2=365,
        )
        assert result["is_exempt_individual"] is False
        assert result["status"] == "nonresident_alien"

    def test_j1_exempt_individual(self):
        """J-1 visa should also be treated as exempt within 5 years per new logic."""
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="J-1",
            first_us_arrival_year=2022,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=0,
        )
        assert result["is_exempt_individual"] is True
        assert result["exempt_visa_type"] == "J-1"
        assert result["status"] == "nonresident_alien"

    def test_fractional_days_dropped(self):
        """Verify IRS integer division rule (fractions dropped)."""
        # Testing the internal SPT day calc
        # e.g., 100 current + 100 prior 1 (100//3 = 33) + 100 prior 2 (100//6 = 16)
        # Total: 100 + 33 + 16 = 149
        calc = SubstantialPresenceCalculator()
        res = calc._compute_spt_days(100, 100, 100)
        assert res == 149


class TestJ1TeacherResearcherWindow:
    """Regression tests: a J-1 teacher/researcher gets a 2-calendar-year
    exempt window (IRC §7701(b)(5)(E)), not the 5-year student window —
    previously the frontend sent a non-standard "J-1-R" visa_type that
    matched nothing, giving these filers ZERO exempt years (worse than
    either window) and risking a wrongly-premature resident_alien
    classification."""

    def setup_method(self):
        self.calc = SubstantialPresenceCalculator()

    def test_j1_teacher_researcher_exempt_within_2_years(self):
        # Arrived 2023, tax year 2024 -> 2 calendar years present. Exempt.
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="J-1",
            visa_subtype="teacher_researcher",
            first_us_arrival_year=2023,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=0,
        )
        assert result["is_exempt_individual"] is True
        assert result["years_in_exempt_status"] == 2

    def test_j1_teacher_researcher_not_exempt_in_3rd_year(self):
        """This is the exact bug: a 3rd-year J-1 researcher must lose
        exemption (2-year window), unlike a 3rd-year J-1 STUDENT who is
        still well within the 5-year window."""
        # Arrived 2022, tax year 2024 -> 3 calendar years present.
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="J-1",
            visa_subtype="teacher_researcher",
            first_us_arrival_year=2022,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=365,
        )
        assert result["is_exempt_individual"] is False
        # No longer exempt -> falls through to real SPT arithmetic.
        # 365 + 365//3 + 365//6 = 365 + 121 + 60 = 546 >= 183 -> resident.
        assert result["status"] == "resident_alien"

    def test_j1_student_subtype_unaffected_still_5_year_window(self):
        """Default visa_subtype="student" (and any non-teacher_researcher
        value) must preserve the existing 5-year J-1 student behavior —
        this fix must not regress the far more common case."""
        # Arrived 2022, tax year 2024 -> 3 calendar years present, well
        # within the 5-year student window.
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="J-1",
            first_us_arrival_year=2022,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=365,
        )
        assert result["is_exempt_individual"] is True
        assert result["status"] == "nonresident_alien"

    def test_f1_visa_type_unaffected_by_teacher_researcher_subtype(self):
        """visa_subtype only matters for J-1 — an F-1 filer must keep the
        5-year window even if visa_subtype is somehow set to
        teacher_researcher (defensive: F-1 has no teacher/researcher
        category at all)."""
        result = self.calc.evaluate_residency(
            tax_year=2024,
            visa_type="F-1",
            visa_subtype="teacher_researcher",
            first_us_arrival_year=2021,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=365,
        )
        # 2021->2024 = 4 calendar years, within the 5-year F-1 window.
        assert result["is_exempt_individual"] is True
        assert result["years_in_exempt_status"] == 4


class TestDualStatusDetection:
    """Phase 2: ``evaluate_residency_with_status_change`` arrival/departure paths."""

    def setup_method(self):
        from datetime import date

        self.calc = SubstantialPresenceCalculator()
        self.date = date

    def test_exempt_individual_never_dual_status(self):
        """An F-1 within the 5-year window is NRA all year — never dual-status."""
        result = self.calc.evaluate_residency_with_status_change(
            tax_year=2025,
            visa_type="F-1",
            first_us_arrival_year=2024,
            days_present_current_year=300,
            days_present_minus_1=200,
            days_present_minus_2=0,
            first_day_in_us_current_year=self.date(2025, 6, 1),
        )
        assert result["is_dual_status"] is False
        assert result["status"] == "nonresident_alien"
        assert result["residency_start_date"] is None

    def test_arrival_year_dual_status(self):
        """H-1B arriving August 2025 with prior US presence — RA partway, NRA Jan-July."""
        result = self.calc.evaluate_residency_with_status_change(
            tax_year=2025,
            visa_type="H-1B",
            first_us_arrival_year=2020,
            days_present_current_year=200,
            days_present_minus_1=200,
            days_present_minus_2=200,
            first_day_in_us_current_year=self.date(2025, 8, 1),
            prior_visa_was_resident=False,
        )
        assert result["is_dual_status"] is True
        assert result["status"] == "dual_status"
        assert result["residency_start_date"] == "2025-08-01"

    def test_departure_year_dual_status(self):
        """Departing September 2025 after being RA last year — RA through Sept, NRA after."""
        result = self.calc.evaluate_residency_with_status_change(
            tax_year=2025,
            visa_type="H-1B",
            first_us_arrival_year=2020,
            days_present_current_year=250,
            days_present_minus_1=365,
            days_present_minus_2=365,
            last_day_in_us_current_year=self.date(2025, 9, 30),
            prior_visa_was_resident=True,
        )
        assert result["is_dual_status"] is True
        assert result["residency_end_date"] == "2025-09-30"

    def test_full_year_resident_not_dual_status(self):
        """RA all year with no arrival or departure mid-year — straight RA, not dual."""
        result = self.calc.evaluate_residency_with_status_change(
            tax_year=2025,
            visa_type="H-1B",
            first_us_arrival_year=2020,
            days_present_current_year=365,
            days_present_minus_1=365,
            days_present_minus_2=365,
            first_day_in_us_current_year=self.date(2025, 1, 1),
            prior_visa_was_resident=True,
        )
        assert result["is_dual_status"] is False
        assert result["status"] == "resident_alien"
