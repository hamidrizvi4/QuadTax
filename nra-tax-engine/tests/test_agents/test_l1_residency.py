"""Tests for the L1 Residency Agent."""

from unittest.mock import MagicMock
import pytest

from src.agents.l1_residency import ResidencyAgent, I94DayCountParams
from src.orchestrator.state import ReturnStateObject


class TestResidencyAgent:
    """Test suite for the LLM-powered Residency Agent."""

    def test_process_residency_f1_exempt(self):
        """Agent should properly feed extracted days to the SPT calculator and mutate state."""

        # 1. Mock the OpenAI Client
        mock_client = MagicMock()
        mock_completion = MagicMock()
        
        # Setup the fake parsed LLM response
        fake_extracted_days = I94DayCountParams(
            days_current_year=300,
            days_minus_1=365,
            days_minus_2=365
        )
        
        # Deep mock the completion choices structure
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.parsed = fake_extracted_days
        
        # Attach the mock to the client's `beta.chat.completions.parse` method
        mock_client.beta.chat.completions.parse.return_value = mock_completion

        # 2. Instantiate Agent with the mock client
        agent = ResidencyAgent(llm_client=mock_client)
        
        # 3. Prepare the state Object
        state = ReturnStateObject()
        
        # 4. Execute the agent process
        updated_state = agent.process_residency(
            i94_ocr_text="FAKE OCR TEXT WITH DATES",
            tax_year=2024,
            visa_type="F-1",
            first_us_arrival_year=2022,  # 3rd year -> exempt!
            current_state=state,
        )

        # 5. Assert the LLM was called correctly
        mock_client.beta.chat.completions.parse.assert_called_once()
        call_kwargs = mock_client.beta.chat.completions.parse.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-2024-08-06"
        assert call_kwargs["response_format"] == I94DayCountParams
        assert "FAKE OCR TEXT WITH DATES" in call_kwargs["messages"][1]["content"]

        # 6. Assert deterministic state mutation happened correctly
        # Arriving 2022 -> filing 2024 is the 3rd year.
        # F-1 student in year 3 is EXEMPT, meaning days count as 0, 
        # so they should be classified as nonresident_alien automatically.
        assert updated_state.residency.status == "nonresident_alien"
        assert updated_state.residency.spt_days_current_year == 300
        assert updated_state.residency.is_exempt_individual is True
        assert updated_state.residency.years_in_exempt_status == 3
        # Ensure layer was marked complete
        assert "L1" in updated_state.completed_layers

    def test_process_residency_h1b_not_exempt(self):
        """Agent should correctly route non-exempt individuals through the math formula."""
        mock_client = MagicMock()
        mock_completion = MagicMock()
        
        # 120 + 360/3 + 360/6 = 120 + 120 + 60 = 300 SPT days -> Resident
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.parsed = I94DayCountParams(
            days_current_year=120,
            days_minus_1=360,
            days_minus_2=360
        )
        mock_client.beta.chat.completions.parse.return_value = mock_completion

        agent = ResidencyAgent(llm_client=mock_client)
        state = ReturnStateObject()

        # H-1B is never exempt
        updated_state = agent.process_residency(
            i94_ocr_text="FAKE RECORD",
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2022,
            current_state=state,
        )

        assert updated_state.residency.status == "resident_alien"
        assert updated_state.residency.is_exempt_individual is False
        assert updated_state.residency.spt_days_current_year == 120
        assert "L1" in updated_state.completed_layers
