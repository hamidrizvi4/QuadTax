"""Tests for the NY tax math (brackets, treaty add-back, allocation, NYC/Yonkers)."""

from decimal import Decimal

import pytest

from src.functions.ny_tax_math import NYTaxCalculator


@pytest.fixture
def calc():
    return NYTaxCalculator(tax_year=2025)


class TestNYTaxMath:
    def test_resident_basic_brackets(self, calc):
        """$30k resident: standard deduction $8k → taxable $22k. NY brackets through 4.5%."""
        r = calc.compute(
            federal_agi=30000.0,
            ny_residency_status="resident",
            filing_status="single",
        )
        # Taxable: $22,000
        #   4.0% on first $8,500 = $340
        #   4.5% on next $3,200 ($8,500→$11,700) = $144
        #   5.25% on next $2,200 ($11,700→$13,900) = $115.50
        #   5.5% on next $8,100 ($13,900→$22,000) = $445.50
        #   Total ≈ $1,045
        assert r.ny_taxable_income == Decimal("22000")
        assert r.ny_tax_resident_basis == pytest.approx(Decimal("1045"), abs=Decimal("1"))

    def test_treaty_addback_increases_ny_agi(self, calc):
        """Federal $25k AGI + $5k treaty addback → NY AGI = $30k."""
        r = calc.compute(
            federal_agi=25000.0,
            federal_treaty_exemption=5000.0,
            ny_residency_status="resident",
        )
        assert r.ny_agi == Decimal("30000")
        assert r.ny_treaty_addback == Decimal("5000")

    def test_nonresident_apportionment(self, calc):
        """F-1 at NYU with $30k wages — 100% NY-source — equals resident tax for that AGI."""
        r = calc.compute(
            federal_agi=30000.0,
            ny_source_income=30000.0,
            ny_residency_status="nonresident",
            filing_status="single",
        )
        assert r.ny_income_percentage == Decimal("1.000000")
        assert r.ny_tax_apportioned == r.ny_tax_resident_basis

    def test_nonresident_partial_ny_source(self, calc):
        """50% NY-source → tax apportioned to 50% of resident-basis tax."""
        r = calc.compute(
            federal_agi=60000.0,
            ny_source_income=30000.0,
            ny_residency_status="nonresident",
            filing_status="single",
        )
        assert r.ny_income_percentage == Decimal("0.500000")
        assert r.ny_tax_apportioned == (r.ny_tax_resident_basis * Decimal("0.5")).quantize(
            Decimal("0.01")
        )

    def test_nyc_resident_pays_nyc_tax(self, calc):
        r = calc.compute(
            federal_agi=30000.0,
            ny_residency_status="resident",
            nyc_resident=True,
        )
        assert r.nyc_tax > Decimal("0")
        assert r.total_ny_state_local == r.ny_tax_apportioned + r.nyc_tax

    def test_non_nyc_resident_pays_no_nyc_tax(self, calc):
        r = calc.compute(
            federal_agi=30000.0,
            ny_residency_status="nonresident",
            ny_source_income=30000.0,
            nyc_resident=False,
        )
        assert r.nyc_tax == Decimal("0")

    def test_yonkers_nonresident_earnings_tax(self, calc):
        r = calc.compute(
            federal_agi=30000.0,
            ny_residency_status="nonresident",
            ny_source_income=30000.0,
            yonkers_nonresident_earnings=20000.0,
        )
        # 0.5% of $20,000 = $100
        assert r.yonkers_tax == Decimal("100.00")
