"""Tests for the L6 Tax Calculation Agent."""

from unittest.mock import patch
import pytest

from src.agents.l6_tax_calc import TaxCalculationAgent
from src.orchestrator.state import ReturnStateObject


class TestTaxCalculationAgent:
    """Test suite for the deterministic L6 wrapper."""

    @patch("src.agents.l6_tax_calc.TaxCalculator")
    def test_process_tax_applies_exemptions(self, MockCalculator):
        """Verify the agent subtracts treaty exemptions before calling the math engine."""
        
        # Setup the mock to check its call arguments later
        mock_instance = MockCalculator.return_value
        mock_instance.calculate_tax_liability.return_value = {
            "eci_tax_liability": 2761.0,
            "fdap_tax_liability": 1400.0,
            "total_tax_liability": 4161.0
        }

        # Setup Dummy State
        state = ReturnStateObject()
        
        # Base Income
        state.income.eci_taxable_total = 30000.0
        state.income.fdap_taxable_total = 10000.0
        
        # Treaty Setup
        state.treaty.is_eligible = True
        state.treaty.applied_to_category = "teaching_research" # Deduct from ECI!
        state.treaty.exempt_amount_applied = 5000.0
        
        # FDAP Rules - Assume F-1 getting remainder taxed at 14%
        state.residency.exempt_visa_type = "F-1"

        # Execute
        agent = TaxCalculationAgent()
        updated_state = agent.process_tax(current_state=state)

        # Assertions
        # math: 30000 ECI - 5000 Treaty = 25000 ECI handed off to Calculator
        # math: 10000 FDAP remains untouched by this particular treaty
        mock_instance.calculate_tax_liability.assert_called_once_with(
            eci_taxable_income=25000.0,
            fdap_taxable_income=10000.0,
            fdap_rate=0.14
        )

        # Assert State was mutated with the hypothetical test outcomes
        assert updated_state.tax.eci_tax_liability == 2761.0
        assert updated_state.tax.total_tax_liability == 4161.0
        assert "L6" in updated_state.completed_layers
