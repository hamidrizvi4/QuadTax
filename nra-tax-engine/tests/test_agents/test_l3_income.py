"""Tests for the L3 Income Agent."""

from unittest.mock import MagicMock
import pytest

from src.agents.l3_income import IncomeAgent, W2Data, Form1042SData
from src.orchestrator.state import ReturnStateObject


class TestIncomeAgent:
    """Test suite for the LLM-powered Income Agent."""

    def test_process_income_routing_and_mutation(self):
        """Verify the agent extracts data via LLM and correctly delegates routing to mutate state."""
        mock_client = MagicMock()
        
        # We will pass 1 W-2 and 2 1042-S forms.
        # The first call will be for the W-2.
        # The second and third calls will be for the 1042-S forms.
        
        # Fake W-2 data
        fake_w2 = W2Data(
            box_1_wages=15000.0,
            box_2_fed_withholding=1500.0,
            box_4_ss_withheld=0.0,
            box_6_medicare_withheld=0.0
        )
        w2_completion = MagicMock()
        w2_completion.choices = [MagicMock()]
        w2_completion.choices[0].message.parsed = fake_w2
        
        # Fake 1042-S Data #1: A standard taxable stipend (Code 16, FDAP)
        fake_1042s_1 = Form1042SData(
            box_1_income_code=16,
            box_2_gross_income=5000.0,
            box_3a_exemption_rate=14.0,
            box_3b_exemption_code="00",
            box_7a_fed_withheld=700.0
        )
        f1042s_1_completion = MagicMock()
        f1042s_1_completion.choices = [MagicMock()]
        f1042s_1_completion.choices[0].message.parsed = fake_1042s_1

        # Fake 1042-S Data #2: Another W-2 equivalent income (Code 18, ECI)
        fake_1042s_2 = Form1042SData(
            box_1_income_code=18,
            box_2_gross_income=2000.0,
            box_3a_exemption_rate=0.0,
            box_3b_exemption_code="00",
            box_7a_fed_withheld=200.0
        )
        f1042s_2_completion = MagicMock()
        f1042s_2_completion.choices = [MagicMock()]
        f1042s_2_completion.choices[0].message.parsed = fake_1042s_2
        
        # Set the side effect to return these consecutively 
        mock_client.beta.chat.completions.parse.side_effect = [
            w2_completion, 
            f1042s_1_completion, 
            f1042s_2_completion
        ]
        
        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()
        
        # Provide 1 w2 string and 2 1042-s strings to trigger 3 LLM calls
        updated_state = agent.process_income(
            w2_ocr_texts=["FAKE W-2 TEXT"],
            form_1042s_ocr_texts=["FAKE 1042-S TEXT 1", "FAKE 1042-S TEXT 2"],
            requires_services=False,
            is_qualified_expense=False, # This means the Code 16 will route to FDAP
            current_state=state
        )
        
        # Asserts on mock LLM calls
        assert mock_client.beta.chat.completions.parse.call_count == 3
        
        # State Assertion:
        # W-2 Wages = 15000
        # 1042-S Gross = 5000 + 2000 = 7000
        # ECI Total = W-2 + Code 18 = 15000 + 2000 = 17000
        # FDAP Total = Code 16 (Not qualified, no services) = 5000
        # Excluded = 0
        assert updated_state.income.total_w2_wages == 15000.0
        assert updated_state.income.total_1042s_gross == 7000.0
        assert updated_state.income.eci_taxable_total == 17000.0
        assert updated_state.income.fdap_taxable_total == 5000.0
        assert updated_state.income.exempt_scholarship_total == 0.0
        assert "L3" in updated_state.completed_layers

    def test_estimated_payments_from_extras_reach_withholding_report(self):
        """Regression test: reconcile() has always accepted an
        estimated_payments param, but nothing passed it — line 26 of the
        1040-NR was hardcoded to 0 regardless of what the filer entered."""
        mock_client = MagicMock()
        w2_completion = MagicMock()
        w2_completion.choices = [MagicMock()]
        w2_completion.choices[0].message.parsed = W2Data(
            box_1_wages=10000.0, box_2_fed_withholding=1000.0,
            box_4_ss_withheld=0.0, box_6_medicare_withheld=0.0,
        )
        mock_client.beta.chat.completions.parse.side_effect = [w2_completion]

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()
        state.extras.made_estimated_federal_payments = True
        state.extras.estimated_federal_payment_amount = 800.0

        updated_state = agent.process_income(
            w2_ocr_texts=["FAKE W-2 TEXT"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        assert updated_state.withholding_report["federal_estimated_payments"] == 800.0

    def test_no_estimated_payments_when_flag_unset(self):
        mock_client = MagicMock()
        w2_completion = MagicMock()
        w2_completion.choices = [MagicMock()]
        w2_completion.choices[0].message.parsed = W2Data(
            box_1_wages=10000.0, box_2_fed_withholding=1000.0,
            box_4_ss_withheld=0.0, box_6_medicare_withheld=0.0,
        )
        mock_client.beta.chat.completions.parse.side_effect = [w2_completion]

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()
        state.extras.estimated_federal_payment_amount = 800.0  # set but flag False

        updated_state = agent.process_income(
            w2_ocr_texts=["FAKE W-2 TEXT"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        assert updated_state.withholding_report["federal_estimated_payments"] == 0.0
