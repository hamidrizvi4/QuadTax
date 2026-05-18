"""Tests for FICA refund detection and owed-FICA computation."""

from decimal import Decimal

import pytest

from src.functions.fica_math import FicaCalculator


@pytest.fixture
def calc():
    return FicaCalculator(tax_year=2025)


class TestFicaRefundDetection:
    def test_exempt_nra_with_withholding_triggers_843(self, calc):
        result = calc.evaluate_fica_refund(
            status="nonresident_alien",
            is_exempt_individual=True,
            raw_ss_withheld=1860.0,
            raw_medicare_withheld=435.0,
        )
        assert result["is_exempt"] is True
        assert result["incorrect_ss_withheld"] == 1860.0
        assert result["incorrect_medicare_withheld"] == 435.0
        assert result["requires_form_843"] is True

    def test_exempt_nra_no_withholding_no_843(self, calc):
        result = calc.evaluate_fica_refund(
            status="nonresident_alien",
            is_exempt_individual=True,
            raw_ss_withheld=0.0,
            raw_medicare_withheld=0.0,
        )
        assert result["requires_form_843"] is False

    def test_resident_alien_path_returns_no_refund(self, calc):
        result = calc.evaluate_fica_refund(
            status="resident_alien",
            is_exempt_individual=False,
            raw_ss_withheld=2000.0,
            raw_medicare_withheld=500.0,
        )
        assert result["is_exempt"] is False
        assert result["requires_form_843"] is False


class TestFicaOwedComputation:
    def test_basic_50k_wages_single(self, calc):
        r = calc.calculate_fica_owed(wages=50000.0, filing_status="single")
        # SS: 50,000 × 6.2% = 3,100
        # Medicare: 50,000 × 1.45% = 725
        # Additional Medicare: 0 (under $200k threshold)
        assert r.social_security_owed == Decimal("3100.00")
        assert r.medicare_owed == Decimal("725.00")
        assert r.additional_medicare_owed == Decimal("0")
        assert r.total_fica_owed == Decimal("3825.00")

    def test_wage_base_caps_social_security(self, calc):
        """SS contributions cap at 6.2% × $176,100 = $10,918.20 for TY2025."""
        r = calc.calculate_fica_owed(wages=300000.0, filing_status="single")
        assert r.social_security_owed == Decimal("10918.20")
        # Medicare uncapped: 300,000 × 1.45% = 4,350
        assert r.medicare_owed == Decimal("4350.00")
        # Additional Medicare: (300,000 − 200,000) × 0.9% = 900
        assert r.additional_medicare_owed == Decimal("900.00")

    def test_additional_medicare_mfs_threshold_is_125k(self, calc):
        r = calc.calculate_fica_owed(wages=200000.0, filing_status="mfs")
        # (200,000 − 125,000) × 0.9% = 675
        assert r.additional_medicare_owed == Decimal("675.00")

    def test_shortfall_when_employer_underwithheld(self, calc):
        r = calc.calculate_fica_owed(
            wages=50000.0,
            filing_status="single",
            already_withheld_ss=2000.0,
            already_withheld_medicare=500.0,
        )
        # owed total = 3,825; already = 2,500; shortfall = 1,325
        assert r.shortfall_vs_withheld == Decimal("1325.00")

    def test_no_shortfall_when_employer_correct(self, calc):
        r = calc.calculate_fica_owed(
            wages=50000.0,
            filing_status="single",
            already_withheld_ss=3100.0,
            already_withheld_medicare=725.0,
        )
        assert r.shortfall_vs_withheld == Decimal("0")
