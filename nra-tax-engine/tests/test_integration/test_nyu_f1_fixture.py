"""Golden fixture: F-1 at NYU year 2, $30k wages, dorm housing.

Acceptance test for Phase 4 (NY pipeline).

Filer profile:
    * Chinese F-1 in NYU dorm year-round (Knight case → NY nonresident).
    * $30,000 W-2 from NYU (100% NY-source).
    * $1,200 NY tax withheld, $600 NYC tax withheld.
    * Treaty Art 20(c) exempts $5k at federal level — but NY adds it back.
    * Expected: federal refund $1,738; NY filed as nonresident on IT-203 with
      treaty add-back; NYC tax = $0 (dorm resident is NOT a NYC resident).
"""

from unittest.mock import MagicMock, patch

from src.agents.l1_residency import I94DayCountParams
from src.agents.l3_income import Form1042SData, W2Data
from src.agents.l4_treaty import TreatyCategoryMapping
from src.orchestrator.engine import TaxEngine


class _MockMsg:
    def __init__(self, p):
        self.parsed = p


class _MockChoice:
    def __init__(self, p):
        self.message = _MockMsg(p)


class _MockResp:
    def __init__(self, p):
        self.choices = [_MockChoice(p)]


def _router(model, messages, response_format, temperature=0.0):
    if response_format == I94DayCountParams:
        return _MockResp(I94DayCountParams(days_current_year=330, days_minus_1=200, days_minus_2=0))
    if response_format == W2Data:
        return _MockResp(
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
        return _MockResp(TreatyCategoryMapping(mapped_category="student_personal_services"))
    raise ValueError(f"Unmocked schema: {response_format}")


class TestNYUFixture:
    @patch("src.orchestrator.engine.FormPopulator.generate_filing_package")
    def test_f1_nyu_dorm_nonresident(self, mock_generate):
        mock_generate.return_value = [
            "outputs/student_1040-NR.pdf",
            "outputs/student_8843.pdf",
            "outputs/student_8833.pdf",
            "outputs/student_843.pdf",
            "outputs/student_IT-203.pdf",
            "outputs/student_IT-203-B.pdf",
        ]
        mock_llm = MagicMock()
        mock_llm.beta.chat.completions.parse.side_effect = _router

        engine = TaxEngine(llm_client=mock_llm)
        pdf_paths, state = engine.run_full_pipeline(
            i94_ocr_text="dummy",
            w2_ocr_texts=["dummy w2"],
            form_1042s_ocr_texts=[],
            mcq_answers={
                "tax_year": 2025,
                "visa_type": "F-1",
                "first_us_arrival_year": 2024,
                "tax_residence_country": "CN",
                "income_description": "Dining hall worker",
                "requires_services": True,
                "is_qualified_expense": False,
                "ny_intake": {
                    "days_in_ny": 330,
                    "has_permanent_abode_in_ny": True,
                    "abode_months_in_year": 12,
                    "is_student_dorm": True,
                    "domiciled_in_ny": False,
                    "ny_work_days": 200,
                    "total_work_days": 200,
                    "employer_in_ny": True,
                    "institution_1042s_in_ny": True,
                    "nyc_address": False,  # Dorm → not a NYC resident
                },
            },
        )

        # --- Federal: same numbers as the Phase 2 China Art 20(c) fixture ---
        assert state.tax.eci_tax_liability == 2762.0
        assert state.tax.refund_or_owed == -1738.0

        # --- NY residency: dorm exclusion → nonresident ---
        assert state.ny.residency_status == "nonresident"
        assert "dormitory" in state.ny.residency_reason.lower() or "knight" in state.ny.residency_reason.lower()
        assert state.ny.nyc_resident is False

        # --- NY allocation: 100% NY-source wages ---
        assert state.ny.ny_source_wages == 30000.0
        assert state.ny.ny_income_percentage == 1.0

        # --- NY treaty add-back: $5k federal exemption added back at state ---
        assert state.ny.ny_treaty_addback == 5000.0
        assert state.ny.ny_agi == 30000.0  # Wages $30k = AGI (no other income)

        # --- NY standard deduction ($8,000 single 2025) ---
        assert state.ny.ny_standard_deduction == 8000.0
        assert state.ny.ny_taxable_income == 22000.0

        # --- NY state tax: ≈ $1,045 (graduated brackets through 5.5%) ---
        assert 1000.0 <= state.ny.ny_tax_apportioned <= 1100.0

        # --- NYC: dorm → not a NYC resident, $0 NYC tax ---
        assert state.ny.nyc_tax == 0.0

        # --- NY withholding: $1,200 NY + $600 NYC = $1,800 ---
        assert state.ny.ny_withholding == 1200.0
        assert state.ny.nyc_withholding == 600.0
        # NY total state+local tax ≈ $1,045; withholding $1,800 → refund of ~$755.
        assert state.ny.ny_refund_or_owed < 0

        # --- Required forms include IT-203 and IT-203-B ---
        assert "IT-203" in state.forms_required
        assert "IT-203-B" in state.forms_required
