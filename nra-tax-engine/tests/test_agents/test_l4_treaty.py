"""Tests for the L4 Treaty Agent."""

from unittest.mock import MagicMock
import pytest

from src.agents.l4_treaty import TreatyAgent, TreatyCategoryMapping
from src.orchestrator.state import ReturnStateObject


class TestTreatyAgent:
    """Test suite for the LLM-powered Treaty semantic routing Agent."""

    def test_process_treaties_teaching_research(self):
        """Verify the agent routes a teaching role to the evaluator and mutates state."""
        
        # 1. Mock the OpenAI Client
        mock_client = MagicMock()
        mock_completion = MagicMock()
        
        # Setup the fake parsed LLM response mapping to 'teaching_research'
        fake_mapping = TreatyCategoryMapping(mapped_category="teaching_research")
        
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.parsed = fake_mapping
        
        # Attach the mock to the client's parse method
        mock_client.beta.chat.completions.parse.return_value = mock_completion

        # 2. Instantiate Agent
        agent = TreatyAgent(llm_client=mock_client)
        
        # 3. Prepare the dummy state
        state = ReturnStateObject()
        state.residency.status = "nonresident_alien"
        state.residency.years_in_exempt_status = 2
        state.income.eci_taxable_total = 30000.0  # teaching_research explicitly checks ECI

        # 4. Execute the agent process
        updated_state = agent.process_treaties(
            tax_residence_country="China",
            income_description="PhD Teaching Assistant Part Time",
            current_state=state,
        )

        # 5. Assert the LLM was called safely
        mock_client.beta.chat.completions.parse.assert_called_once()
        
        # 6. Assess the deterministic mutations
        # China's teaching/research article 19 grants unlimited exemption for 3 years
        assert updated_state.treaty.is_eligible is True
        assert updated_state.treaty.country == "China"
        assert updated_state.treaty.article_number == "19"
        assert updated_state.treaty.exempt_amount_applied == 30000.0 # Unlimited applied to ECI amount
        
        # Forms and Layer markers
        assert "8833" in updated_state.forms_required
        assert "L4" in updated_state.completed_layers

    def test_process_treaties_skips_resident_alien(self):
        """Ensure the agent short-circuits execution if the student is a resident alien."""
        mock_client = MagicMock()
        agent = TreatyAgent(llm_client=mock_client)
        
        state = ReturnStateObject()
        state.residency.status = "resident_alien" # Treaties generally skipped here
        
        updated_state = agent.process_treaties(
            tax_residence_country="India",
            income_description="Generic Work",
            current_state=state,
        )
        
        # LLM MUST NOT BE CALLED
        mock_client.beta.chat.completions.parse.assert_not_called()
        
        # Ensure it was marked skipped
        assert "L4_Skipped" in updated_state.completed_layers
        assert updated_state.treaty.is_eligible is False
