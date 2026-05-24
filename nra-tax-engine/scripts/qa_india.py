#!/usr/bin/env python3
"""End-to-end QA: a random Indian F-1 student.

India is the UNIQUE treaty country: Article 21(2) does NOT exempt student
wages — it lets the student claim the same standard deduction as a US
single filer ($15,000 for TY2025). This is different from China (which
caps a wage exemption at $5,000). This script exercises that path and
hand-verifies the math.

Filer: Arjun Sharma, Indian national, F-1, arrived Aug 2023 (year 3 of 5),
graduate research assistant at a NY university, living in a dorm.

W-2 (from the university):
    Box 1  Wages:               $28,000.00
    Box 2  Federal withholding:  $4,200.00 (15%)
    Box 4  SS withheld:          $1,736.00  ← INCORRECT: F-1 exempt
    Box 6  Medicare withheld:      $406.00  ← INCORRECT: F-1 exempt
    Box 17 NY state income tax:  $1,050.00
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agents.l1_residency import I94DayCountParams
from src.agents.l3_income import Form1042SData, W2Data
from src.agents.l4_treaty import TreatyCategoryMapping
from src.assembly.forms import compute as compute_form
from src.intake.intake_schema import (
    IntakeIdentity,
    IntakeIncome,
    IntakeNYContext,
    IntakePayload,
    IntakeResidency,
)
from src.intake.mcq_router import MCQRouter
from src.orchestrator.engine import TaxEngine


def _llm_router(model, messages, response_format, temperature=0.0):
    msg = MagicMock()
    if response_format == I94DayCountParams:
        msg.parsed = I94DayCountParams(days_current_year=340, days_minus_1=260, days_minus_2=140)
    elif response_format == W2Data:
        msg.parsed = W2Data(
            box_1_wages=28000.0,
            box_2_fed_withholding=4200.0,
            box_3_ss_wages=28000.0,
            box_4_ss_withheld=1736.0,
            box_5_medicare_wages=28000.0,
            box_6_medicare_withheld=406.0,
            box_17_state_income_tax=1050.0,
            box_18_local_wages=28000.0,
            box_19_local_income_tax=0.0,
            box_20_locality_name="",
        )
    elif response_format == Form1042SData:
        msg.parsed = Form1042SData(
            box_1_income_code=16, box_2_gross_income=0.0, box_3a_exemption_rate=0.0,
            box_3b_exemption_code="00", box_7a_fed_withheld=0.0, chapter_indicator=3,
        )
    elif response_format == TreatyCategoryMapping:
        msg.parsed = TreatyCategoryMapping(mapped_category="student_personal_services")
    else:
        raise ValueError(f"Unmocked schema: {response_format}")
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _hr(title: str) -> None:
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def main() -> int:
    intake = IntakePayload(
        identity=IntakeIdentity(
            first_name="Arjun", last_name="Sharma", date_of_birth="2000-07-22",
            ssn="", itin="998765432",
            country_of_citizenship="IN", country_of_tax_residence="IN",
            passport_number="Z3456789", passport_country="IN",
            us_address_line1="Univ Graduate Housing", us_address_line2="Bldg C Rm 214",
            us_city="New York", us_state="NY", us_zip="10027",
            foreign_address_line1="14 MG Road", foreign_city="Bengaluru",
            foreign_country="IN", foreign_postal_code="560001",
            occupation="Graduate Research Assistant",
            daytime_phone="646-555-0188", email="as9911@univ.edu",
            filing_status="single",
        ),
        residency=IntakeResidency(
            tax_year=2025, visa_type="F-1", visa_subtype="student",
            first_us_arrival_year=2023,
        ),
        income=IntakeIncome(
            income_description="Graduate research assistant — hourly campus wages",
            requires_services=True, is_qualified_expense=False,
        ),
        ny=IntakeNYContext(
            days_in_ny=340, has_permanent_abode_in_ny=True, abode_months_in_year=12,
            is_student_dorm=True, domiciled_in_ny=False,
            ny_work_days=210, total_work_days=210,
            employer_in_ny=True, institution_1042s_in_ny=True, nyc_address=False,
        ),
    )

    router = MCQRouter()
    seeded = router.populate_state(intake)
    mcq_dict = router.to_mcq_answers(intake)

    _hr("FILER")
    print(f"  {intake.identity.first_name} {intake.identity.last_name} — India, F-1, arrived {intake.residency.first_us_arrival_year} (year 3 of 5)")
    print(f"  ITIN {intake.identity.itin}, dorm housing at a NY university")
    print(f"  W-2: $28,000 wages, $4,200 fed wh, $1,736 SS, $406 Medicare, $1,050 NY tax")

    mock_llm = MagicMock()
    mock_llm.beta.chat.completions.parse.side_effect = _llm_router
    with patch("src.orchestrator.engine.FormPopulator.generate_filing_package") as mg:
        mg.return_value = []
        engine = TaxEngine(llm_client=mock_llm)
        _paths, state = engine.run_full_pipeline(
            i94_ocr_text="dummy", w2_ocr_texts=["dummy w2"], form_1042s_ocr_texts=[],
            mcq_answers=mcq_dict, initial_state=seeded,
        )

    _hr("L1 — RESIDENCY")
    print(f"  status={state.residency.status}  exempt={state.residency.is_exempt_individual}  year={state.residency.years_in_exempt_status}")

    _hr("L3 — INCOME + WITHHOLDING")
    print(f"  ECI wages           = ${state.income.eci_taxable_total:,.2f}")
    wh = state.withholding_report
    print(f"  fed withholding     = ${wh['federal_w2']:,.2f}")
    print(f"  SS / Medicare wh    = ${wh['ss_withheld_w2']:,.2f} / ${wh['medicare_withheld_w2']:,.2f}")
    print(f"  NY state tax wh     = ${wh['state_income_tax_w2']:,.2f}")

    _hr("L4 — TREATY (India Art 21(2) = standard deduction, NOT wage exemption)")
    print(f"  is_eligible         = {state.treaty.is_eligible}")
    print(f"  country / article   = {state.treaty.country} {state.treaty.article_number}")
    print(f"  applied_to_category = {state.treaty.applied_to_category}")
    print(f"  requires_form_8833  = {state.treaty.requires_form_8833}")
    print(f"  exempt_amount_applied (state field) = ${state.treaty.exempt_amount_applied:,.2f}")
    for b in state.treaty.applied_benefits:
        print(f"    benefit: {b['country_iso2']} {b['article_id']}  exempt=${b['exempt_amount']:,.2f}")

    _hr("L6 — TAX (hand-trace)")
    print(f"  gross ECI                 = $28,000.00")
    print(f"  India Art 21(2) → apply $15,000 single standard deduction (NOT a wage exemption)")
    print(f"  taxable income            = $28,000 − $15,000 = $13,000.00")
    print(f"  2025 single brackets on $13,000:")
    print(f"    10% × $11,925              = $1,192.50")
    print(f"    12% × $1,075 (= 13,000−11,925) = $129.00")
    print(f"    expected total             = $1,321.50 → $1,322")
    print(f"  engine eci_tax_liability  = ${state.tax.eci_tax_liability:,.2f}")
    print(f"  engine total_tax_liability= ${state.tax.total_tax_liability:,.2f}")

    _hr("L7 — CREDITS")
    print(f"  withholding credits = ${state.tax.total_withholding_credits:,.2f}")
    print(f"  refund_or_owed      = ${state.tax.refund_or_owed:,.2f}  → federal refund ${-state.tax.refund_or_owed:,.2f}")

    _hr("L8 — FICA")
    fica_total = state.fica.incorrect_ss_withheld + state.fica.incorrect_medicare_withheld
    print(f"  is_exempt={state.fica.is_exempt}  requires_843={state.fica.requires_form_843}")
    print(f"  FICA refund claim   = ${fica_total:,.2f}")

    _hr("L9 — NY (India Art 21(2) is NOT added back — it's a deduction, not a treaty wage exemption)")
    print(f"  residency_status    = {state.ny.residency_status}")
    print(f"  ny_treaty_addback   = ${state.ny.ny_treaty_addback:,.2f}  (should be $0 for India 21(2))")
    print(f"  ny_agi              = ${state.ny.ny_agi:,.2f}")
    print(f"  ny_standard_deduction = ${state.ny.ny_standard_deduction:,.2f}")
    print(f"  ny_taxable_income   = ${state.ny.ny_taxable_income:,.2f}")
    print(f"  ny_tax_apportioned  = ${state.ny.ny_tax_apportioned:,.2f}")
    print(f"  ny_withholding      = ${state.ny.ny_withholding:,.2f}")
    print(f"  ny_refund_or_owed   = ${state.ny.ny_refund_or_owed:,.2f}")

    _hr("FORMS — key lines")
    print(f"  forms_required: {state.forms_required}")
    f1040 = compute_form("1040-NR", state)
    print(f"  1040-NR line_1a_wages              = {f1040['line_1a_wages']!r}")
    print(f"  1040-NR line_1k_treaty_exempt_wages = {f1040['line_1k_treaty_exempt_wages']!r}  (should be empty — India has NO wage exemption)")
    print(f"  1040-NR line_12_deduction          = {f1040['line_12_deduction']!r}  (the $15k standard deduction)")
    print(f"  1040-NR line_15_taxable_income     = {f1040['line_15_taxable_income']!r}")
    print(f"  1040-NR line_16_tax                = {f1040['line_16_tax']!r}")
    print(f"  1040-NR line_33_refund             = {f1040['line_33_refund']!r}")
    sch_oi = compute_form("Schedule-OI", state)
    print(f"  Schedule-OI Item L treaty rows     = {sch_oi['item_L_treaty_rows']}")

    _hr("FINAL")
    print(f"  Federal refund: ${-state.tax.refund_or_owed:,.2f}")
    print(f"  FICA refund:    ${fica_total:,.2f}")
    print(f"  NY refund:      ${-state.ny.ny_refund_or_owed:,.2f}")
    print(f"  requires_human_review: {state.requires_human_review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
