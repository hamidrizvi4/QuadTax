"""Tests for the Progressive Tax Math Evaluator."""

import pytest
from src.functions.tax_math import TaxCalculator


class TestTaxCalculator:
    """Test suite for the deterministic tax bracket iterations."""

    def setup_method(self):
        self.calc = TaxCalculator()

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
