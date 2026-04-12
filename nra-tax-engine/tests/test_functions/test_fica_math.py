"""Tests for FICA Math Evaluation."""

from src.functions.fica_math import FicaCalculator

class TestFicaCalculator:
    """Test suite for FICA refund math."""

    def setup_method(self):
        self.calc = FicaCalculator()

    def test_exempt_nonresident(self):
        result = self.calc.evaluate_fica_refund(
            status="nonresident_alien",
            is_exempt_individual=True,
            raw_ss_withheld=100.0,
            raw_medicare_withheld=23.0
        )
        assert result["is_exempt"] is True
        assert result["requires_form_843"] is True
        assert result["incorrect_ss_withheld"] == 100.0

    def test_resident_alien_pays_fica(self):
        result = self.calc.evaluate_fica_refund(
            status="resident_alien",
            is_exempt_individual=False,
            raw_ss_withheld=100.0,
            raw_medicare_withheld=23.0
        )
        assert result["is_exempt"] is False
        assert result["requires_form_843"] is False
