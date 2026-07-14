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

    def test_process_residency_reads_visa_subtype_from_state(self):
        """Regression test: visa_subtype (already seeded onto state by
        MCQRouter before L1 runs) must actually reach the SPT calculator —
        a J-1 teacher/researcher in year 3 must lose exemption (2-year
        window), unlike a J-1 student in year 3 (still within 5 years)."""
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.parsed = I94DayCountParams(
            days_current_year=365, days_minus_1=365, days_minus_2=365
        )
        mock_client.beta.chat.completions.parse.return_value = mock_completion

        agent = ResidencyAgent(llm_client=mock_client)
        state = ReturnStateObject()
        state.residency.visa_subtype = "teacher_researcher"

        updated_state = agent.process_residency(
            i94_ocr_text="FAKE RECORD",
            tax_year=2024,
            visa_type="J-1",
            first_us_arrival_year=2022,  # 3rd calendar year
            current_state=state,
        )

        # 3rd year exceeds the 2-year teacher/researcher window -> not exempt,
        # falls through to real SPT math (365+121+60=546 >= 183) -> resident.
        assert updated_state.residency.is_exempt_individual is False
        assert updated_state.residency.status == "resident_alien"


class TestDualStatusWiring:
    """Dedicated pass proving evaluate_residency_with_status_change() is
    actually wired end-to-end through the agent — the calculator method
    already had test coverage in isolation, but l1_residency.py never
    called it (dead code from the pipeline's perspective) until this fix."""

    @staticmethod
    def _mock_client(days_current, days_minus_1, days_minus_2):
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.parsed = I94DayCountParams(
            days_current_year=days_current,
            days_minus_1=days_minus_1,
            days_minus_2=days_minus_2,
        )
        mock_client.beta.chat.completions.parse.return_value = mock_completion
        return mock_client

    def test_arrival_year_dual_status_detected(self):
        """H-1B arriving mid-year, first year ever in the US, with enough
        presence to meet SPT -> dual status (NRA before arrival, RA after)."""
        agent = ResidencyAgent(llm_client=self._mock_client(200, 0, 0))
        state = ReturnStateObject()
        state.residency.first_us_entry_date = "2024-08-01"
        state.residency.is_still_in_us = True

        updated_state = agent.process_residency(
            i94_ocr_text="FAKE RECORD",
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2024,  # first-ever year == tax year
            current_state=state,
        )

        assert updated_state.residency.is_dual_status is True
        assert updated_state.residency.status == "dual_status"
        assert updated_state.residency.residency_start_date == "2024-08-01"
        assert "L1" in updated_state.completed_layers

    def test_departure_year_dual_status_detected(self):
        """Was a resident alien last year, leaves the US partway through
        this year -> dual status (RA before departure, NRA after)."""
        agent = ResidencyAgent(llm_client=self._mock_client(250, 365, 365))
        state = ReturnStateObject()
        state.residency.prior_year_residency_status = "resident_alien"
        state.residency.is_still_in_us = False
        state.residency.intended_departure_date = "2024-09-30"

        updated_state = agent.process_residency(
            i94_ocr_text="FAKE RECORD",
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2020,
            current_state=state,
        )

        assert updated_state.residency.is_dual_status is True
        assert updated_state.residency.residency_end_date == "2024-09-30"

    def test_continuous_presence_not_dual_status(self):
        """Regression: a filer present for years with no reported gap must
        NOT trigger arrival-year detection just because first_us_entry_date
        happens to be set from an earlier year's original arrival — the
        agent only treats it as this year's first day when
        first_us_arrival_year == tax_year."""
        agent = ResidencyAgent(llm_client=self._mock_client(365, 365, 365))
        state = ReturnStateObject()
        state.residency.first_us_entry_date = "2020-03-01"  # arrival was in 2020
        state.residency.is_still_in_us = True

        updated_state = agent.process_residency(
            i94_ocr_text="FAKE RECORD",
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2020,  # NOT the current tax year
            current_state=state,
        )

        assert updated_state.residency.is_dual_status is False
        assert updated_state.residency.status == "resident_alien"

    def test_exempt_individual_never_dual_status_even_with_dates_set(self):
        """Defensive: an F-1 within the exempt window is NRA all year
        regardless of any arrival/departure dates supplied."""
        agent = ResidencyAgent(llm_client=self._mock_client(300, 200, 0))
        state = ReturnStateObject()
        state.residency.first_us_entry_date = "2024-06-01"
        state.residency.is_still_in_us = True

        updated_state = agent.process_residency(
            i94_ocr_text="FAKE RECORD",
            tax_year=2024,
            visa_type="F-1",
            first_us_arrival_year=2024,
            current_state=state,
        )

        assert updated_state.residency.is_exempt_individual is True
        assert updated_state.residency.is_dual_status is False
        assert updated_state.residency.status == "nonresident_alien"

    def test_dual_status_blocks_assembly_via_validator(self):
        """End-to-end: a dual-status detection from the real wiring must
        actually reach validate_post_l1's existing gate, not just set a
        field nobody reads."""
        from src.orchestrator.validators import validate_post_l1

        agent = ResidencyAgent(llm_client=self._mock_client(200, 0, 0))
        state = ReturnStateObject()
        state.residency.first_us_entry_date = "2024-08-01"
        state.residency.is_still_in_us = True

        updated_state = agent.process_residency(
            i94_ocr_text="FAKE RECORD",
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2024,
            current_state=state,
        )
        validate_post_l1(updated_state)
        assert any(
            "Dual-status" in r for r in updated_state.requires_human_review
        )
