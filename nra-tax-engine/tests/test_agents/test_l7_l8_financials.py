"""Tests for L7 (Credits) and L8 (FICA) Financial Orchestrators."""

from src.agents.l7_credits import CreditsAgent
from src.agents.l8_fica import FicaAgent
from src.orchestrator.state import ReturnStateObject


class TestFinancialLayers:
    """Test suite ensuring the final financial tally agents operate correctly."""

    def test_l7_and_l8_pipeline(self):
        """Simulate a full run of the final ledger stages on an exempt student."""
        # 1. State Construction
        state = ReturnStateObject()

        # Mock Upstream Liabilities
        state.tax.total_tax_liability = 1000.0

        # Mock Withholdings Pipeline
        state.income.total_w2_withholding = 1500.0
        state.income.total_1042s_withholding = 0.0

        # Mock FICA Errors
        state.residency.status = "nonresident_alien"
        state.residency.is_exempt_individual = True
        state.income.raw_ss_withheld = 500.0
        state.income.raw_medicare_withheld = 100.0

        # 2. Run Layer 7 (Credits and Federal Balance)
        agent_l7 = CreditsAgent()
        intermediate_state = agent_l7.process_credits(current_state=state)

        # Asserts for L7
        # Liability (1000) - Withholding (1500) = Owed (-500), which represents a $500 refund
        assert intermediate_state.tax.refund_or_owed == -500.0
        assert intermediate_state.tax.total_withholding_credits == 1500.0
        assert "L7" in intermediate_state.completed_layers

        # 3. Run Layer 8 (FICA)
        agent_l8 = FicaAgent()
        final_state = agent_l8.process_fica(current_state=intermediate_state)

        # Asserts for L8
        assert final_state.fica.is_exempt is True
        assert final_state.fica.incorrect_ss_withheld == 500.0
        assert final_state.fica.incorrect_medicare_withheld == 100.0
        
        # 843 Must be added
        assert "843" in final_state.forms_required
        assert "L8" in final_state.completed_layers
