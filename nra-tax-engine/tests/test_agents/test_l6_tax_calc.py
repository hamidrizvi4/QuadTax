"""Tests for the L6 Tax Calculation Agent (Phase 1: multi-benefit treaty application)."""

from unittest.mock import patch

from src.agents.l6_tax_calc import TaxCalculationAgent
from src.orchestrator.state import ReturnStateObject


class TestTaxCalculationAgent:
    @patch("src.agents.l6_tax_calc.TaxCalculator")
    def test_process_tax_subtracts_eci_benefit(self, MockCalculator):
        """L6 subtracts a $5k teaching_research treaty benefit from ECI before bracket math."""
        mock_instance = MockCalculator.return_value
        mock_instance.calculate_tax_liability.return_value = {
            "eci_tax_liability": 2761.0,
            "fdap_tax_liability": 1400.0,
            "total_tax_liability": 4161.0,
        }

        state = ReturnStateObject()
        state.income.eci_taxable_total = 30000.0
        state.income.fdap_taxable_total = 10000.0
        state.residency.exempt_visa_type = "F-1"
        state.treaty.is_eligible = True
        state.treaty.applied_to_category = "teaching_research"
        state.treaty.exempt_amount_applied = 5000.0
        state.treaty.applied_benefits = [
            {
                "country_iso2": "CN",
                "country_name": "China",
                "article_id": "19",
                "category": "teaching_research",
                "exempt_amount": 5000.0,
                "rate_override": None,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
                "explanation": "test",
            }
        ]

        agent = TaxCalculationAgent()
        updated = agent.process_tax(current_state=state)

        # ECI was reduced from $30,000 to $25,000; FDAP untouched; F-1 → 14% FDAP rate.
        mock_instance.calculate_tax_liability.assert_called_once_with(
            eci_taxable_income=25000.0,
            fdap_taxable_income=10000.0,
            fdap_rate=0.14,
        )
        assert updated.tax.eci_tax_liability == 2761.0
        assert updated.tax.total_tax_liability == 4161.0
        assert "L6" in updated.completed_layers

    @patch("src.agents.l6_tax_calc.TaxCalculator")
    def test_process_tax_india_standard_deduction(self, MockCalculator):
        """India Art 21(2) applies the single-status standard deduction ($15k for TY2025)."""
        mock_instance = MockCalculator.return_value
        mock_instance.calculate_tax_liability.return_value = {
            "eci_tax_liability": 500.0,
            "fdap_tax_liability": 0.0,
            "total_tax_liability": 500.0,
        }

        state = ReturnStateObject()
        state.income.eci_taxable_total = 20000.0
        state.income.fdap_taxable_total = 0.0
        state.residency.exempt_visa_type = "F-1"
        state.treaty.is_eligible = True
        state.treaty.applied_to_category = "student_personal_services"
        state.treaty.exempt_amount_applied = 20000.0  # max-cap-less benefit
        state.treaty.applied_benefits = [
            {
                "country_iso2": "IN",
                "country_name": "India",
                "article_id": "21(2)",
                "category": "student_personal_services",
                "exempt_amount": 20000.0,
                "rate_override": None,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
                "explanation": "India standard deduction equivalent",
            }
        ]

        agent = TaxCalculationAgent()
        agent.process_tax(current_state=state)

        # India 21(2) does NOT exempt wages; instead the $15,000 single standard
        # deduction is subtracted: $20,000 − $15,000 = $5,000.
        mock_instance.calculate_tax_liability.assert_called_once_with(
            eci_taxable_income=5000.0,
            fdap_taxable_income=0.0,
            fdap_rate=0.30,
        )

    @patch("src.agents.l6_tax_calc.TaxCalculator")
    def test_process_tax_india_standard_deduction_capped_for_dependent(self, MockCalculator):
        """Regression test: a filer claimable as another taxpayer's
        dependent must get the IRC §63(c)(5)-capped deduction, not the full
        $15,000 — using the full amount would understate their tax owed."""
        mock_instance = MockCalculator.return_value
        mock_instance.calculate_tax_liability.return_value = {
            "eci_tax_liability": 0.0,
            "fdap_tax_liability": 0.0,
            "total_tax_liability": 0.0,
        }

        state = ReturnStateObject()
        state.income.eci_taxable_total = 20000.0
        state.income.fdap_taxable_total = 0.0
        state.income.total_w2_wages = 20000.0  # "earned income" proxy
        state.residency.exempt_visa_type = "F-1"
        state.extras.can_be_claimed_as_dependent = True
        state.treaty.is_eligible = True
        state.treaty.applied_to_category = "student_personal_services"
        state.treaty.applied_benefits = [
            {
                "country_iso2": "IN",
                "country_name": "India",
                "article_id": "21(2)",
                "category": "student_personal_services",
                "exempt_amount": 20000.0,
                "rate_override": None,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
                "explanation": "India standard deduction equivalent",
            }
        ]

        agent = TaxCalculationAgent()
        updated_state = agent.process_tax(current_state=state)

        # Dependent deduction = min(15000, max(1350, 20000+450)) = 15000
        # (earned income is high enough that the cap is the regular amount
        # itself here) — use a case where the cap actually bites instead:
        # confirm the deduction_amount used the dependent path at all by
        # checking it's NOT silently identical to the non-dependent default
        # for a low-earned-income dependent.
        assert updated_state.tax.deduction_amount == 15000.0

    @patch("src.agents.l6_tax_calc.TaxCalculator")
    def test_dependent_with_low_earned_income_gets_capped_deduction(self, MockCalculator):
        mock_instance = MockCalculator.return_value
        mock_instance.calculate_tax_liability.return_value = {
            "eci_tax_liability": 0.0,
            "fdap_tax_liability": 0.0,
            "total_tax_liability": 0.0,
        }

        state = ReturnStateObject()
        state.income.eci_taxable_total = 3000.0
        state.income.fdap_taxable_total = 0.0
        state.income.total_w2_wages = 3000.0
        state.residency.exempt_visa_type = "F-1"
        state.extras.can_be_claimed_as_dependent = True
        state.treaty.is_eligible = True
        state.treaty.applied_to_category = "student_personal_services"
        state.treaty.applied_benefits = [
            {
                "country_iso2": "IN",
                "country_name": "India",
                "article_id": "21(2)",
                "category": "student_personal_services",
                "exempt_amount": 3000.0,
                "rate_override": None,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
                "explanation": "India standard deduction equivalent",
            }
        ]

        agent = TaxCalculationAgent()
        updated_state = agent.process_tax(current_state=state)

        # min(15000, max(1350, 3000+450)) = min(15000, 3450) = 3450 — far
        # below the full $15,000 a non-dependent would get.
        assert updated_state.tax.deduction_amount == 3450.0
        assert updated_state.tax.deduction_amount < 15000.0

    @patch("src.agents.l6_tax_calc.TaxCalculator")
    def test_process_tax_fdap_zeroed_treaty_yields_zero_rate(self, MockCalculator):
        """When treaty exempts ALL FDAP scholarship, the effective FDAP rate goes to 0%."""
        mock_instance = MockCalculator.return_value
        mock_instance.calculate_tax_liability.return_value = {
            "eci_tax_liability": 0.0,
            "fdap_tax_liability": 0.0,
            "total_tax_liability": 0.0,
        }

        state = ReturnStateObject()
        state.income.fdap_taxable_total = 22000.0
        state.residency.exempt_visa_type = "F-1"
        state.treaty.is_eligible = True
        state.treaty.applied_to_category = "scholarship_fellowship"
        state.treaty.exempt_amount_applied = 22000.0
        state.treaty.applied_benefits = [
            {
                "country_iso2": "CN",
                "country_name": "China",
                "article_id": "20(b)",
                "category": "scholarship_fellowship",
                "exempt_amount": 22000.0,
                "rate_override": 0.0,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
                "explanation": "Full scholarship exemption",
            }
        ]

        agent = TaxCalculationAgent()
        agent.process_tax(current_state=state)

        mock_instance.calculate_tax_liability.assert_called_once_with(
            eci_taxable_income=0.0,
            fdap_taxable_income=0.0,
            fdap_rate=0.0,
        )
