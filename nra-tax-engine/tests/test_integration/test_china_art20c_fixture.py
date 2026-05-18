"""Golden fixture: China F-1 year 2 with $30k W-2 wages → $5k Art 20(c) exempt.

Phase 2 acceptance test from the plan. Validates the full DAG end-to-end:
    L1 → SPT places filer as exempt NRA (year 2 of 5).
    L3 → W-2 OCR yields $30k box 1, $4,500 box 2 fed withholding,
          $1,860 box 4 SS, $435 box 6 Medicare.
    L3 → withholding reconciler aggregates all sources.
    L4 → LLM classifies as student_personal_services; evaluator returns
          China Art 20(c) capped at $5k with Form 8833 trigger.
    L6 → ECI = $30k − $5k = $25k; no standard deduction; tax at NRA single
          brackets for TY2025.
    L7 → refund or owed reflects fed withholding from reconciler.
    L8 → exempt + $1,860 SS + $435 Medicare withheld → Form 843 path.
"""

from unittest.mock import MagicMock, patch

from src.agents.l1_residency import I94DayCountParams
from src.agents.l3_income import Form1042SData, W2Data
from src.agents.l4_treaty import TreatyCategoryMapping
from src.orchestrator.engine import TaxEngine


class MockMessage:
    def __init__(self, parsed_obj):
        self.parsed = parsed_obj


class MockChoice:
    def __init__(self, parsed_obj):
        self.message = MockMessage(parsed_obj)


class MockParseResponse:
    def __init__(self, parsed_obj):
        self.choices = [MockChoice(parsed_obj)]


def _llm_router(model, messages, response_format, temperature=0.0):
    if response_format == I94DayCountParams:
        return MockParseResponse(
            I94DayCountParams(days_current_year=300, days_minus_1=200, days_minus_2=0)
        )
    if response_format == W2Data:
        return MockParseResponse(
            W2Data(
                box_1_wages=30000.0,
                box_2_fed_withholding=4500.0,
                box_3_ss_wages=30000.0,
                box_4_ss_withheld=1860.0,
                box_5_medicare_wages=30000.0,
                box_6_medicare_withheld=435.0,
                box_17_state_income_tax=1200.0,
                box_18_local_wages=30000.0,
                box_19_local_income_tax=600.0,
                box_20_locality_name="NYC",
            )
        )
    if response_format == Form1042SData:
        return MockParseResponse(
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
        return MockParseResponse(TreatyCategoryMapping(mapped_category="student_personal_services"))
    raise ValueError(f"Unmocked response_format: {response_format}")


class TestChinaArt20cFixture:
    @patch("src.orchestrator.engine.FormPopulator.generate_filing_package")
    def test_china_student_5k_wage_exemption(self, mock_generate):
        mock_generate.return_value = [
            "outputs/student_name_1040-NR.pdf",
            "outputs/student_name_8843.pdf",
            "outputs/student_name_8833.pdf",
            "outputs/student_name_843.pdf",
        ]
        mock_llm = MagicMock()
        mock_llm.beta.chat.completions.parse.side_effect = _llm_router

        engine = TaxEngine(llm_client=mock_llm)
        pdf_paths, state = engine.run_full_pipeline(
            i94_ocr_text="dummy i94",
            w2_ocr_texts=["dummy w2"],
            form_1042s_ocr_texts=[],
            mcq_answers={
                "tax_year": 2025,
                "visa_type": "F-1",
                "first_us_arrival_year": 2024,
                "tax_residence_country": "CN",
                "income_description": "On-campus dining hall worker",
                "requires_services": True,
                "is_qualified_expense": False,
            },
        )

        # --- L1: NRA, exempt, year 2 of 5 ----------------------------------
        assert state.residency.status == "nonresident_alien"
        assert state.residency.is_exempt_individual is True
        assert state.residency.years_in_exempt_status == 2

        # --- L3: income totals + withholding reconciliation ----------------
        assert state.income.total_w2_wages == 30000.0
        assert state.income.eci_taxable_total == 30000.0  # before treaty
        assert state.withholding_report["federal_w2"] == 4500.0
        assert state.withholding_report["ss_withheld_w2"] == 1860.0
        assert state.withholding_report["medicare_withheld_w2"] == 435.0
        assert state.withholding_report["state_income_tax_w2"] == 1200.0
        assert state.withholding_report["local_income_tax_w2"] == 600.0

        # --- L4: China Art 20(c) capped at $5k -----------------------------
        assert state.treaty.is_eligible is True
        assert state.treaty.country == "CN"
        assert state.treaty.article_number == "20(c)"
        assert state.treaty.exempt_amount_applied == 5000.0
        assert state.treaty.requires_form_8833 is True
        assert "8833" in state.forms_required

        # Saving-clause exception flag is present on the benefit (would carry
        # over to year-6 resident-alien case).
        assert any(
            b["applies_after_saving_clause"] is False  # NRA in year 2, so False here
            and b["article_id"] == "20(c)"
            for b in state.treaty.applied_benefits
        )

        # --- L6: ECI reduced by $5k, taxed at NRA single TY2025 brackets ---
        # $25,000 across the 2025 brackets:
        #   10% on first $11,925 = $1,192.50
        #   12% on remaining $13,075 = $1,569.00
        # Total ECI tax = $2,761.50 → rounded $2,762
        assert state.tax.eci_tax_liability == 2762.0
        assert state.tax.fdap_tax_liability == 0.0
        assert state.tax.total_tax_liability == 2762.0

        # --- L7: refund = withholding − liability --------------------------
        # Convention: refund_or_owed = liability − credits; negative means refund.
        # $2,762 − $4,500 = −$1,738 → refund of $1,738.
        assert state.tax.total_withholding_credits == 4500.0
        assert state.tax.refund_or_owed == -1738.0

        # --- L8: FICA exempt, Form 843 path --------------------------------
        assert state.fica.is_exempt is True
        assert state.fica.incorrect_ss_withheld == 1860.0
        assert state.fica.incorrect_medicare_withheld == 435.0
        assert state.fica.requires_form_843 is True
        assert "843" in state.forms_required

        # --- Forms required summary ----------------------------------------
        pdf_blob = " ".join(pdf_paths)
        assert "1040-NR" in pdf_blob
        assert "8843" in pdf_blob
        assert "8833" in pdf_blob
        assert "843" in pdf_blob
