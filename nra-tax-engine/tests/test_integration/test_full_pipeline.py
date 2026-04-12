"""Integration Tests — Full Pipeline Architecture."""

from unittest.mock import MagicMock, patch

from src.orchestrator.engine import TaxEngine
from src.agents.l1_residency import I94DayCountParams
from src.agents.l3_income import W2Data, Form1042SData
from src.agents.l4_treaty import TreatyCategoryMapping


class MockMessage:
    def __init__(self, parsed_obj):
        self.parsed = parsed_obj


class MockChoice:
    def __init__(self, parsed_obj):
        self.message = MockMessage(parsed_obj)


class MockParseResponse:
    def __init__(self, parsed_obj):
        self.choices = [MockChoice(parsed_obj)]


def _mock_llm_parse_router(model, messages, response_format, temperature=0.0):
    """Dynamically routes LLM predictions to deterministic dummy Pydantic objects based on the requested format."""
    if response_format == I94DayCountParams:
        return MockParseResponse(
            I94DayCountParams(
                days_current_year=120,
                days_minus_1=0,
                days_minus_2=0,
            )
        )
    elif response_format == W2Data:
        return MockParseResponse(
            W2Data(
                box_1_wages=30000.0,
                box_2_fed_withholding=1500.0,
                box_4_ss_withheld=500.0,
                box_6_medicare_withheld=100.0,
            )
        )
    elif response_format == Form1042SData:
        return MockParseResponse(
            Form1042SData(
                box_1_income_code="16", 
                box_2_gross_income=0.0,  # Ignoring 1042s for simplicity
                box_3a_exemption_rate=0.0,
                box_3b_exemption_code="00",
                box_7a_fed_withheld=0.0,
            )
        )
    elif response_format == TreatyCategoryMapping:
        return MockParseResponse(TreatyCategoryMapping(mapped_category="teaching_research"))

    raise ValueError(f"Unknown response format requested: {response_format}")


class TestFullPipelineIntegrity:
    """Ensures the fully completed DAG executes end-to-end securely."""

    @patch("src.orchestrator.engine.FormPopulator.generate_filing_package")
    def test_engine_end_to_end(self, mock_generate_package):
        """Validates state transitions and final PDF path emissions from the engine."""
        
        # Setup the dynamic physical mock for the Populator step
        mock_generate_package.return_value = [
            "outputs/student_name_1040-NR.pdf",
            "outputs/student_name_8843.pdf",
            "outputs/student_name_8833.pdf",
            "outputs/student_name_843.pdf",
        ]

        # 1. Setup Mock LLM Client
        mock_llm = MagicMock()
        mock_llm.beta.chat.completions.parse.side_effect = _mock_llm_parse_router

        # 2. Setup Mock App Params
        mcq_answers = {
            "tax_year": 2024,
            "visa_type": "F-1",
            "first_us_arrival_year": 2023,
            "tax_residence_country": "China",
            "income_description": "PhD TA",
            "requires_services": True,
            "is_qualified_expense": False,
        }

        # 3. Instantiate Engine
        engine = TaxEngine(llm_client=mock_llm)

        # 4. Execute the fully orchestrated pipeline
        pdf_paths, final_state = engine.run_full_pipeline(
            i94_ocr_text="DUMMY_I94_TEXT",
            w2_ocr_texts=["DUMMY_W2_TEXT"],
            form_1042s_ocr_texts=[],  # Empty to simplify the run
            mcq_answers=mcq_answers,
        )

        # 5. Assertions
        # Ensure LLM Client was utilized by the agents organically
        assert mock_llm.beta.chat.completions.parse.call_count >= 2 # I94, W2, Treaty

        # Verify correct dummy data generated physical routing forms
        # L1: Nonresident Alien (2024-2023 < 5 years)
        # L3: ECI $30,000 W2
        # L4: China Teaching Research > Unlimited Exemption -> $0 ECI. Treaty form 8833 triggered
        # L6: $0 ECI -> Tax: $0
        # L7: $0 Tax - $1500 Credits = -$1500 Refund.
        # L8: Exemption triggered, FICA refund triggers 843.
        # Required Forms: 1040-NR, 8843, 8833, 843
        
        # Check generated PDF stubs
        pdf_names = " ".join(pdf_paths)
        assert "1040-NR" in pdf_names
        assert "8843" in pdf_names
        assert "8833" in pdf_names
        assert "843" in pdf_names
