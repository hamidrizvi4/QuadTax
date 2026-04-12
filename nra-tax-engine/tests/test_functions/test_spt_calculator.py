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
