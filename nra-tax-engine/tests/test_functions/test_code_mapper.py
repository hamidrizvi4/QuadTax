"""Tests for the IncomeCodeMapper — routing 1042-S income to proper tax treatment."""

import pytest
from src.functions.code_mapper import IncomeCodeMapper


class TestIncomeCodeMapper:
    """Test suite for 1042-S Code Mapper."""

    def setup_method(self):
        self.mapper = IncomeCodeMapper()

    def test_eci_routing(self):
        """Standard ECI codes should route to ECI."""
        result = self.mapper.route_1042s_income(
            income_code=18,
            gross_amount=3000.0,
            requires_services=True,  # Doesn't override generic ECI routing
            is_qualified_expense=False,
        )
        assert result["category"] == "ECI"
        assert result["taxable_amount"] == 3000.0
        assert "statutory_rate" not in result

    def test_fdap_routing(self):
        """Standard FDAP codes should route to FDAP."""
        result = self.mapper.route_1042s_income(
            income_code="12", # Test string casting
            gross_amount=1500.50,
            requires_services=False,
            is_qualified_expense=False,
        )
        assert result["category"] == "FDAP"
        assert result["taxable_amount"] == 1500.50
        assert "statutory_rate" not in result

    def test_code_36_routing(self):
        """Code 36 (Bank Deposit Interest) is strictly excluded."""
        result = self.mapper.route_1042s_income(
            income_code=36,
            gross_amount=50.0,
            requires_services=False,
            is_qualified_expense=False,
        )
        assert result["category"] == "EXCLUDED"
        assert result["taxable_amount"] == 0.0

    def test_code_16_qualified_expense(self):
        """Code 16 scholarship used for tuition is excluded (IRC 117)."""
        result = self.mapper.route_1042s_income(
            income_code=16,
            gross_amount=20000.0,
            requires_services=False,
            is_qualified_expense=True,
        )
        assert result["category"] == "EXCLUDED"
        assert result["taxable_amount"] == 0.0
        
    def test_code_16_requires_services(self):
        """Code 16 scholarship requiring services is compensation (ECI)."""
        result = self.mapper.route_1042s_income(
            income_code=16,
            gross_amount=25000.0,
            requires_services=True,
            is_qualified_expense=False,
        )
        assert result["category"] == "ECI"
        assert result["taxable_amount"] == 25000.0
        assert "statutory_rate" not in result

    def test_code_16_standard_stipend(self):
        """Code 16 scholarship (no services, no tuition) is FDAP with 14% rate."""
        result = self.mapper.route_1042s_income(
            income_code=16,
            gross_amount=5000.0,
            requires_services=False,
            is_qualified_expense=False,
        )
        assert result["category"] == "FDAP"
        assert result["taxable_amount"] == 5000.0
        assert result["statutory_rate"] == 0.14

    def test_invalid_code_type(self):
        """Non-integer codes shouldn't map successfully."""
        with pytest.raises(ValueError, match="Invalid income code format"):
            self.mapper.route_1042s_income("invalid", 100.0, False, False)

    def test_unknown_code(self):
        """Any 1042-S code outside the explicit lists should raise an error."""
        with pytest.raises(ValueError, match="Unknown or unsupported"):
            self.mapper.route_1042s_income(99, 1000.0, False, False)


class TestExtendedFDAPCodes:
    """Phase 2: cover the additional 1042-S codes added to the FDAP set."""

    def setup_method(self):
        self.mapper = IncomeCodeMapper()

    def test_code_22_interest_to_controlling_foreign_corp(self):
        r = self.mapper.route_1042s_income(22, 1000.0, False, False)
        assert r["category"] == "FDAP"

    def test_code_24_qie_capital_gain_distribution(self):
        r = self.mapper.route_1042s_income(24, 500.0, False, False)
        assert r["category"] == "FDAP"

    def test_code_27_pship_distribution(self):
        r = self.mapper.route_1042s_income(27, 750.0, False, False)
        assert r["category"] == "FDAP"

    def test_code_30_oid(self):
        r = self.mapper.route_1042s_income(30, 200.0, False, False)
        assert r["category"] == "FDAP"

    def test_substitute_payment_codes_33_34_35(self):
        for code in (33, 34, 35):
            r = self.mapper.route_1042s_income(code, 100.0, False, False)
            assert r["category"] == "FDAP"

    def test_publicly_offered_security_codes_51_52_53_54(self):
        for code in (51, 52, 53, 54):
            r = self.mapper.route_1042s_income(code, 100.0, False, False)
            assert r["category"] == "FDAP"
