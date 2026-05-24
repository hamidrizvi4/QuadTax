"""Integration: human-in-loop gate blocks assembly until reviewed."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.l1_residency import I94DayCountParams
from src.agents.l3_income import Form1042SData, W2Data
from src.agents.l4_treaty import TreatyCategoryMapping
from src.orchestrator.engine import OrchestrationError, TaxEngine


class _MockMsg:
    def __init__(self, p):
        self.parsed = p


class _MockChoice:
    def __init__(self, p):
        self.message = _MockMsg(p)


class _MockResp:
    def __init__(self, p):
        self.choices = [_MockChoice(p)]


def _router_w2_oversize(model, messages, response_format, temperature=0.0):
    if response_format == I94DayCountParams:
        return _MockResp(
            I94DayCountParams(days_current_year=300, days_minus_1=200, days_minus_2=0)
        )
    if response_format == W2Data:
        # $100 million wages — well beyond the reasonability ceiling.
        return _MockResp(
            W2Data(
                box_1_wages=100_000_000.0,
                box_2_fed_withholding=0.0,
                box_3_ss_wages=100_000_000.0,
                box_4_ss_withheld=0.0,
                box_5_medicare_wages=100_000_000.0,
                box_6_medicare_withheld=0.0,
            )
        )
    if response_format == Form1042SData:
        return _MockResp(
            Form1042SData(
                box_1_income_code=16,
                box_2_gross_income=0.0,
                box_3a_exemption_rate=0.0,
                box_3b_exemption_code="00",
                box_7a_fed_withheld=0.0,
                chapter_indicator=3,
            )
        )
    if response_format == TreatyCategoryMapping:
        return _MockResp(
            TreatyCategoryMapping(mapped_category="student_personal_services")
        )
    raise ValueError(f"unmocked {response_format}")


class TestHumanInLoopGate:
    @patch("src.orchestrator.engine.FormPopulator.generate_filing_package")
    def test_extreme_wages_block_assembly(self, mock_generate):
        mock_generate.return_value = []
        mock_llm = MagicMock()
        mock_llm.beta.chat.completions.parse.side_effect = _router_w2_oversize

        engine = TaxEngine(llm_client=mock_llm)
        mcq = {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2024,
            "tax_residence_country": "CN",
            "income_description": "TA",
            "requires_services": True,
            "is_qualified_expense": False,
        }
        with pytest.raises(OrchestrationError) as excinfo:
            engine.run_full_pipeline(
                i94_ocr_text="x",
                w2_ocr_texts=["x"],
                form_1042s_ocr_texts=[],
                mcq_answers=mcq,
            )
        assert "human review" in str(excinfo.value).lower()

    @patch("src.orchestrator.engine.FormPopulator.generate_filing_package")
    def test_force_assembly_overrides_gate(self, mock_generate):
        mock_generate.return_value = ["outputs/x_1040-NR.fieldmap.json"]
        mock_llm = MagicMock()
        mock_llm.beta.chat.completions.parse.side_effect = _router_w2_oversize

        engine = TaxEngine(llm_client=mock_llm, force_assembly=True)
        mcq = {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2024,
            "tax_residence_country": "CN",
            "income_description": "TA",
            "requires_services": True,
            "is_qualified_expense": False,
        }
        pdf_paths, state = engine.run_full_pipeline(
            i94_ocr_text="x",
            w2_ocr_texts=["x"],
            form_1042s_ocr_texts=[],
            mcq_answers=mcq,
        )
        # Gate was bypassed; review reasons still recorded for audit.
        assert state.ready_for_assembly is True
        assert any("reasonability ceiling" in r for r in state.requires_human_review)
        assert len(state.audit_trail) > 0


class TestAuditTrailPersists:
    @patch("src.orchestrator.engine.FormPopulator.generate_filing_package")
    def test_each_layer_records_an_entry(self, mock_generate):
        """The orchestrator's _run_layer wrapper appends one audit entry per layer."""
        mock_generate.return_value = []
        mock_llm = MagicMock()

        def router_normal(model, messages, response_format, temperature=0.0):
            if response_format == I94DayCountParams:
                return _MockResp(
                    I94DayCountParams(days_current_year=300, days_minus_1=200, days_minus_2=0)
                )
            if response_format == W2Data:
                return _MockResp(
                    W2Data(
                        box_1_wages=30000.0,
                        box_2_fed_withholding=4500.0,
                        box_3_ss_wages=30000.0,
                        box_4_ss_withheld=1860.0,
                        box_5_medicare_wages=30000.0,
                        box_6_medicare_withheld=435.0,
                    )
                )
            if response_format == Form1042SData:
                return _MockResp(
                    Form1042SData(
                        box_1_income_code=16,
                        box_2_gross_income=0.0,
                        box_3a_exemption_rate=0.0,
                        box_3b_exemption_code="00",
                        box_7a_fed_withheld=0.0,
                        chapter_indicator=3,
                    )
                )
            if response_format == TreatyCategoryMapping:
                return _MockResp(
                    TreatyCategoryMapping(mapped_category="student_personal_services")
                )
            raise ValueError()

        mock_llm.beta.chat.completions.parse.side_effect = router_normal
        engine = TaxEngine(llm_client=mock_llm)
        _paths, state = engine.run_full_pipeline(
            i94_ocr_text="x",
            w2_ocr_texts=["x"],
            form_1042s_ocr_texts=[],
            mcq_answers={
                "tax_year": 2025,
                "visa_type": "F-1",
                "first_us_arrival_year": 2024,
                "tax_residence_country": "CN",
                "income_description": "Campus job",
                "requires_services": True,
                "is_qualified_expense": False,
            },
        )
        layers_seen = {entry["layer"] for entry in state.audit_trail}
        assert {"L1", "L3", "L4", "L6", "L7", "L8"}.issubset(layers_seen)
