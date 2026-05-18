"""Tests for the Progressive Tax Math Evaluator."""

import pytest
from src.functions.tax_math import TaxCalculator


class TestTaxCalculator:
    """Test suite for the deterministic tax bracket iterations (TY2025 single default)."""

    def setup_method(self):
        self.calc = TaxCalculator()  # defaults to TY2025 / single

    def test_eci_base_bracket(self):
        """Test $10,000 ECI: Fully contained within the 10% bracket."""
        # 10,000 * 0.10 = 1000
        result = self.calc.calculate_tax_liability(
            eci_taxable_income=10000.0,
            fdap_taxable_income=0.0,
            fdap_rate=0.30
        )
        assert result["eci_tax_liability"] == 1000.0
        assert result["fdap_tax_liability"] == 0.0
        assert result["total_tax_liability"] == 1000.0

    def test_eci_bracket_crossing(self):
        """Test $50,000 ECI: Crosses the 10%, 12%, and 22% brackets."""
        # Brackets:
        # 10% on first $11,925 = $1,192.50
        # 12% on next ($48,475 - $11,925) = 12% of $36,550 = $4,386.00
        # 22% on remaining ($50,000 - $48,475) = 22% of $1,525 = $335.50
        # Total ECI tax = 1192.50 + 4386.00 + 335.50 = 5914.00
        result = self.calc.calculate_tax_liability(
            eci_taxable_income=50000.0,
            fdap_taxable_income=0.0,
            fdap_rate=0.30
        )
        assert result["eci_tax_liability"] == 5914.0

    def test_pure_fdap_student_stipend(self):
        """Test $10,000 FDAP at the student 14% rate with no ECI."""
        # 10,000 * 0.14 = 1400
        result = self.calc.calculate_tax_liability(
            eci_taxable_income=0.0,
            fdap_taxable_income=10000.0,
            fdap_rate=0.14
        )
        assert result["eci_tax_liability"] == 0.0
        assert result["fdap_tax_liability"] == 1400.0
        assert result["total_tax_liability"] == 1400.0


class TestTaxCalculatorFilingStatusRouting:
    """Verify the calculator picks the correct bracket table per filing status."""

    def test_mfs_top_bracket_kicks_in_earlier(self):
        """MFS 37% starts at $375,800 in 2025; single's starts at $626,350."""
        mfs = TaxCalculator(tax_year=2025, filing_status="mfs")
        single = TaxCalculator(tax_year=2025, filing_status="single")

        # At $400,000 ECI, MFS has already entered the 37% bracket; single is still 35%.
        mfs_result = mfs.calculate_tax_liability(400000.0, 0.0, 0.0)
        single_result = single.calculate_tax_liability(400000.0, 0.0, 0.0)
        assert mfs_result["eci_tax_liability"] > single_result["eci_tax_liability"]

    def test_qss_first_bracket_doubled(self):
        """QSS 10% bracket runs to $23,850 (vs $11,925 single)."""
        qss = TaxCalculator(tax_year=2025, filing_status="qss")
        # $20,000 falls entirely in the 10% bracket for QSS.
        result = qss.calculate_tax_liability(20000.0, 0.0, 0.0)
        assert result["eci_tax_liability"] == 2000.0

    def test_invalid_filing_status_rejected(self):
        with pytest.raises(ValueError):
            TaxCalculator(filing_status="hoh")  # NRA cannot file HOH
