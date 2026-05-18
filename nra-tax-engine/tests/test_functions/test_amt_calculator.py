"""Tests for the AMT calculator (Form 6251 math)."""

from decimal import Decimal

import pytest

from src.functions.amt_calculator import AMTCalculator


@pytest.fixture
def calc():
    return AMTCalculator(tax_year=2025)


class TestAMT:
    def test_low_income_no_amt(self, calc):
        """A typical student return — taxable income well under the exemption — owes no AMT."""
        r = calc.compute(taxable_income=25000, regular_tax=2762, filing_status="single")
        assert r.binds is False
        assert r.amt_owed == Decimal("0")

    def test_exemption_phaseout_does_not_engage_below_threshold(self, calc):
        """Exemption remains at the full $88,100 below the $626,350 phase-out start."""
        r = calc.compute(taxable_income=100000, regular_tax=12000, filing_status="single")
        assert r.exemption == Decimal("88100")

    def test_exemption_phases_out_above_threshold(self, calc):
        """Above the phase-out threshold the exemption shrinks by 25% of the excess."""
        r = calc.compute(
            taxable_income=700000,
            regular_tax=200000,
            filing_status="single",
        )
        # Excess over $626,350 = $73,650; phase-out = 25% × 73,650 = $18,412.50
        # Exemption = 88,100 − 18,412.50 = $69,687.50
        assert r.exemption == Decimal("69687.50")

    def test_high_income_amt_can_bind(self, calc):
        """A high-income filer with a low regular tax may owe AMT."""
        r = calc.compute(taxable_income=350000, regular_tax=10000, filing_status="single")
        assert r.tentative_minimum_tax > Decimal("10000")
        assert r.binds is True
        assert r.amt_owed > Decimal("0")

    def test_mfs_threshold_is_different(self, calc):
        """MFS uses half the kink ($119,550) and half the phase-out where applicable."""
        r = calc.compute(taxable_income=200000, regular_tax=20000, filing_status="mfs")
        assert r.amti == Decimal("200000")
