#!/usr/bin/env python3
"""End-to-end QA: trace a realistic Chinese F-1 NYU return through the pipeline.

Filer profile:
    Wei Chen, Chinese national, F-1 visa, arrived August 2023 (year 3 of 5),
    living in NYU dorm, working as on-campus teaching assistant.

W-2 boxes (from NYU):
    Box 1  Wages:               $32,500.00
    Box 2  Federal withholding:  $4,875.00 (15%)
    Box 3  SS wages:            $32,500.00
    Box 4  SS withheld:          $2,015.00  ← INCORRECT: F-1 exempt
    Box 5  Medicare wages:      $32,500.00
    Box 6  Medicare withheld:      $471.25  ← INCORRECT: F-1 exempt
    Box 17 NY state income tax:  $1,300.00
    Box 19 NYC local income tax:   $650.00  ← dorm resident is NOT NYC resident

The script runs the orchestrator with mocked LLM responses (no API key
needed) and prints each layer's output so we can verify math by hand.
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
from src.intake.ocr_parser import DocumentParser
from src.orchestrator.engine import TaxEngine


# Realistic W-2 OCR text — what pdfplumber would extract from a real W-2 PDF.
W2_OCR_TEXT = """
Form W-2 Wage and Tax Statement   2025

a Employee's social security number: XXX-XX-XXXX
b Employer EIN: 13-5562308
c Employer's name, address, and ZIP code:
   New York University
   70 Washington Square South
   New York, NY 10012

d Control number: 2025-N-018372
e Employee name: Wei Chen
f Employee address: NYU Bobst Hall, 110 W 3rd St, New York, NY 10012

1  Wages, tips, other compensation:        32500.00
2  Federal income tax withheld:             4875.00
3  Social security wages:                  32500.00
4  Social security tax withheld:            2015.00
5  Medicare wages and tips:                32500.00
6  Medicare tax withheld:                    471.25
7  Social security tips:                       0.00
8  Allocated tips:                             0.00
10 Dependent care benefits:                    0.00
11 Nonqualified plans:                         0.00
12a Code DD (cost of employer-sponsored health coverage):   8420.00

13 Statutory employee: [ ]   Retirement plan: [X]   Third-party sick pay: [ ]
14 Other: NY DBL 0.60

15 State: NY   Employer state ID: 13-5562308
16 State wages, tips, etc.:           32500.00
17 State income tax:                   1300.00
18 Local wages, tips, etc.:           32500.00
19 Local income tax:                    650.00
20 Locality name: NYC
"""


# Mocked LLM responses corresponding to the W-2 text above.
def _llm_router(model, messages, response_format, temperature=0.0):
    msg = MagicMock()

    if response_format == I94DayCountParams:
        # Real I-94 record: arrived Aug 21 2023, departed for break May 15-Aug 20, 2024,
        # back Aug 21. Net: 2025 = full year ≈ 330 days; 2024 ≈ 250; 2023 ≈ 130.
        msg.parsed = I94DayCountParams(
            days_current_year=330,
            days_minus_1=250,
            days_minus_2=130,
        )
    elif response_format == W2Data:
        msg.parsed = W2Data(
            box_1_wages=32500.0,
            box_2_fed_withholding=4875.0,
            box_3_ss_wages=32500.0,
            box_4_ss_withheld=2015.0,
            box_5_medicare_wages=32500.0,
            box_6_medicare_withheld=471.25,
            box_17_state_income_tax=1300.0,
            box_18_local_wages=32500.0,
            box_19_local_income_tax=650.0,
            box_20_locality_name="NYC",
        )
    elif response_format == Form1042SData:
        msg.parsed = Form1042SData(
            box_1_income_code=16,
            box_2_gross_income=0.0,
            box_3a_exemption_rate=0.0,
            box_3b_exemption_code="00",
            box_7a_fed_withheld=0.0,
            chapter_indicator=3,
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
            first_name="Wei",
            last_name="Chen",
            date_of_birth="2001-03-14",
            itin="912345678",  # No SSN — first-time filer
            country_of_citizenship="CN",
            country_of_tax_residence="CN",
            passport_number="EA1234567",
            passport_country="CN",
            us_address_line1="NYU Bobst Hall",
            us_address_line2="110 W 3rd St",
            us_city="New York",
            us_state="NY",
            us_zip="10012",
            foreign_address_line1="No. 23 Wuhua Street",
            foreign_city="Beijing",
            foreign_country="CN",
            foreign_postal_code="100007",
            occupation="Graduate Teaching Assistant",
            daytime_phone="212-555-0123",
            email="wc1234@nyu.edu",
            filing_status="single",
        ),
        residency=IntakeResidency(
            tax_year=2025,
            visa_type="F-1",
            visa_subtype="student",
            first_us_arrival_year=2023,
        ),
        income=IntakeIncome(
            income_description="Graduate teaching assistant at NYU — paid hourly",
            requires_services=True,
            is_qualified_expense=False,
        ),
        ny=IntakeNYContext(
            days_in_ny=330,
            has_permanent_abode_in_ny=True,
            abode_months_in_year=12,
            is_student_dorm=True,         # Knight case → NY nonresident
            domiciled_in_ny=False,
            ny_work_days=200,
            total_work_days=200,
            employer_in_ny=True,
            institution_1042s_in_ny=True,
            nyc_address=False,             # Dorm → not NYC resident
        ),
    )

    # ------------------------------------------------------------------
    _hr("STAGE 1 — INTAKE")
    # ------------------------------------------------------------------
    router = MCQRouter()
    seeded = router.populate_state(intake)
    mcq_dict = router.to_mcq_answers(intake)
    print(f"Filer:           {intake.identity.first_name} {intake.identity.last_name}")
    print(f"Country:         {intake.identity.country_of_tax_residence}")
    print(f"Visa:            {intake.residency.visa_type}  (arrived {intake.residency.first_us_arrival_year})")
    print(f"Tax year:        {intake.residency.tax_year}")
    print(f"Filing status:   {intake.identity.filing_status}")
    print(f"TIN:             ITIN {intake.identity.itin}")
    print(f"US address:      {intake.identity.us_address_line1}, {intake.identity.us_city} {intake.identity.us_state} {intake.identity.us_zip}")
    print(f"Foreign address: {intake.identity.foreign_address_line1}, {intake.identity.foreign_city} {intake.identity.foreign_country}")
    print(f"NY intake:       dorm={intake.ny.is_student_dorm}, days={intake.ny.days_in_ny}, NYC={intake.ny.nyc_address}")

    # ------------------------------------------------------------------
    _hr("STAGE 2 — OCR (pdfplumber → raw text)")
    # ------------------------------------------------------------------
    print("Simulated W-2 OCR text (what pdfplumber would extract from a real PDF):")
    for line in W2_OCR_TEXT.strip().split("\n"):
        print(f"  {line}")

    # ------------------------------------------------------------------
    _hr("STAGE 3 — LLM extracts typed Pydantic models from OCR text")
    # ------------------------------------------------------------------
    mock_llm = MagicMock()
    mock_llm.beta.chat.completions.parse.side_effect = _llm_router

    # Show what the LLM extraction returns for the W-2.
    w2 = _llm_router(None, None, W2Data, 0.0).choices[0].message.parsed
    print(f"W2Data extracted by LLM (gpt-4o-2024-08-06, temperature=0):")
    for field, value in w2.model_dump().items():
        print(f"  {field:<30} = {value}")

    # ------------------------------------------------------------------
    _hr("STAGE 4 — Run the full L1→L9 pipeline")
    # ------------------------------------------------------------------
    with patch("src.orchestrator.engine.FormPopulator.generate_filing_package") as mg:
        mg.return_value = []  # Skip PDF writing; templates aren't vendored
        engine = TaxEngine(llm_client=mock_llm)
        _paths, state = engine.run_full_pipeline(
            i94_ocr_text="dummy I-94 OCR text",
            w2_ocr_texts=[W2_OCR_TEXT],
            form_1042s_ocr_texts=[],
            mcq_answers=mcq_dict,
            initial_state=seeded,
        )

    # ------------------------------------------------------------------
    _hr("STAGE 5 — Per-layer trace")
    # ------------------------------------------------------------------
    print("L1 — Residency (SubstantialPresenceCalculator):")
    print(f"  status                  = {state.residency.status}")
    print(f"  is_exempt_individual    = {state.residency.is_exempt_individual}")
    print(f"  exempt_visa_type        = {state.residency.exempt_visa_type}")
    print(f"  years_in_exempt_status  = {state.residency.years_in_exempt_status}")
    print(f"  spt_days_current_year   = {state.residency.spt_days_current_year}")
    print("  → F-1 in year 3 of 5 — automatic NRA under IRC §7701(b)(5).")

    print("\nL3 — Income (IncomeAgent → IncomeCodeMapper → WithholdingReconciler):")
    print(f"  total_w2_wages          = ${state.income.total_w2_wages:,.2f}")
    print(f"  eci_taxable_total       = ${state.income.eci_taxable_total:,.2f}")
    print(f"  fdap_taxable_total      = ${state.income.fdap_taxable_total:,.2f}")
    wh = state.withholding_report
    print(f"  withholding_report:")
    print(f"    federal_w2            = ${wh['federal_w2']:,.2f}")
    print(f"    ss_withheld_w2        = ${wh['ss_withheld_w2']:,.2f}  (will refund via 843)")
    print(f"    medicare_withheld_w2  = ${wh['medicare_withheld_w2']:,.2f}  (will refund via 843)")
    print(f"    state_income_tax_w2   = ${wh['state_income_tax_w2']:,.2f}  (NY)")
    print(f"    local_income_tax_w2   = ${wh['local_income_tax_w2']:,.2f}  (NYC)")
    print(f"    federal_total         = ${wh['federal_total']:,.2f}")

    print("\nL4 — Treaty (TreatyAgent → TreatyEvaluator):")
    print(f"  is_eligible             = {state.treaty.is_eligible}")
    print(f"  country                 = {state.treaty.country}")
    print(f"  article_number          = {state.treaty.article_number}")
    print(f"  exempt_amount_applied   = ${state.treaty.exempt_amount_applied:,.2f}")
    print(f"  applied_to_category     = {state.treaty.applied_to_category}")
    print(f"  requires_form_8833      = {state.treaty.requires_form_8833}")
    for b in state.treaty.applied_benefits:
        print(f"  benefit detail:")
        print(f"    article             = {b['country_iso2']} {b['article_id']}")
        print(f"    rate_override       = {b['rate_override']}")
        print(f"    saving_clause_kept  = {b['applies_after_saving_clause']}")
        print(f"    explanation         = {b['explanation']}")

    print("\nL6 — Tax Calculation (TaxCalculationAgent → TaxCalculator):")
    print("  Hand-trace:")
    print(f"    gross ECI               = ${state.income.total_w2_wages:,.2f}")
    print(f"    − treaty exemption      = ${state.treaty.exempt_amount_applied:,.2f}  (China Art 20(c) $5k cap)")
    net_eci = state.income.total_w2_wages - state.treaty.exempt_amount_applied
    print(f"    = net ECI               = ${net_eci:,.2f}")
    print(f"    − standard deduction    = $0.00  (NRA default; only India treaty allows it)")
    print(f"    2025 single brackets on ${net_eci:,.0f}:")
    print(f"      10% × $11,925            = $1,192.50")
    twelve_pct_chunk = net_eci - 11925
    print(f"      12% × ${twelve_pct_chunk:,.0f} (= ${net_eci:,.0f} − $11,925) = ${twelve_pct_chunk * 0.12:,.2f}")
    expected_eci_tax = 1192.50 + (twelve_pct_chunk * 0.12)
    print(f"      Total                       = ${expected_eci_tax:,.2f} → rounds to ${round(expected_eci_tax):,}")
    print(f"  state.tax.eci_tax_liability   = ${state.tax.eci_tax_liability:,.2f}")
    print(f"  state.tax.fdap_tax_liability  = ${state.tax.fdap_tax_liability:,.2f}")
    print(f"  state.tax.total_tax_liability = ${state.tax.total_tax_liability:,.2f}")

    print("\nL7 — Credits (CreditsAgent):")
    print(f"  total_withholding_credits = ${state.tax.total_withholding_credits:,.2f}")
    print(f"  refund_or_owed            = ${state.tax.refund_or_owed:,.2f}  (negative = refund)")
    print(f"  → Federal refund of ${-state.tax.refund_or_owed:,.2f}")

    print("\nL8 — FICA (FicaAgent → FicaCalculator):")
    print(f"  is_exempt               = {state.fica.is_exempt}")
    print(f"  incorrect_ss_withheld   = ${state.fica.incorrect_ss_withheld:,.2f}")
    print(f"  incorrect_medicare      = ${state.fica.incorrect_medicare_withheld:,.2f}")
    print(f"  requires_form_843       = {state.fica.requires_form_843}")
    fica_total = state.fica.incorrect_ss_withheld + state.fica.incorrect_medicare_withheld
    print(f"  → FICA refund claim of ${fica_total:,.2f} via Form 843")

    print("\nL9 — NY pipeline (NYAgent):")
    print(f"  residency_status        = {state.ny.residency_status}")
    print(f"  reason                  = {state.ny.residency_reason}")
    print(f"  days_in_ny              = {state.ny.days_in_ny}")
    print(f"  nyc_resident            = {state.ny.nyc_resident}")
    print(f"  ny_treaty_addback       = ${state.ny.ny_treaty_addback:,.2f}")
    print(f"  ny_agi                  = ${state.ny.ny_agi:,.2f}  (federal AGI post-treaty + add-back)")
    print(f"  ny_standard_deduction   = ${state.ny.ny_standard_deduction:,.2f}")
    print(f"  ny_taxable_income       = ${state.ny.ny_taxable_income:,.2f}")
    print(f"  ny_tax_resident_basis   = ${state.ny.ny_tax_resident_basis:,.2f}")
    print(f"  ny_income_percentage    = {state.ny.ny_income_percentage:.4f}  (= NY-source / NY AGI)")
    print(f"  ny_tax_apportioned      = ${state.ny.ny_tax_apportioned:,.2f}")
    print(f"  nyc_tax                 = ${state.ny.nyc_tax:,.2f}  (dorm → $0)")
    print(f"  ny_withholding          = ${state.ny.ny_withholding:,.2f}")
    print(f"  nyc_withholding         = ${state.ny.nyc_withholding:,.2f}")
    print(f"  ny_refund_or_owed       = ${state.ny.ny_refund_or_owed:,.2f}")

    print("\nPhase-3 add-ons:")
    print(f"  AMT binds?              = {state.amt.get('binds')}  (low income → no AMT)")
    print(f"  ITIN W-7 needed?        = {state.itin_eligibility.get('needs_w7')}  (has ITIN already → False)")
    print(f"  estimated_tax_penalty   = safe-harbor met = {state.estimated_tax_penalty.get('safe_harbor_met')}")

    print("\nHuman-in-loop gate:")
    print(f"  requires_human_review   = {state.requires_human_review}")
    print(f"  ready_for_assembly      = {state.ready_for_assembly}")

    # ------------------------------------------------------------------
    _hr("STAGE 6 — Form field maps (what gets written to each IRS PDF)")
    # ------------------------------------------------------------------
    print("Forms required:", state.forms_required)
    print("\nForm 1040-NR (federal main):")
    f1040 = compute_form("1040-NR", state)
    for k in (
        "last_name", "first_name_mi", "identifying_number", "us_state",
        "filing_status_single", "line_1a_wages", "line_1k_treaty_exempt_wages",
        "line_11_agi", "line_12_deduction", "line_15_taxable_income",
        "line_16_tax", "line_24_total_tax", "line_25a_w2_withholding",
        "line_33_total_payments", "line_34_overpaid", "line_37_owed",
    ):
        if k in f1040:
            print(f"  {k:<32} = {f1040[k]!r}")

    print("\nSchedule OI Item L (Treaty disclosure table):")
    sch_oi = compute_form("Schedule-OI", state)
    for row in sch_oi.get("item_L_treaty_rows", []):
        print(f"  country={row['country']!r}  article={row['article']}  exempt this yr=${row['amount_this_year']:,.0f}")
    print(f"  Days in US this year: {sch_oi['item_H_days_current_year']}")
    print(f"  Visa: {sch_oi['item_E_visa_type']}")

    print("\nForm 8833 (Treaty disclosure under IRC §6114):")
    f8833 = compute_form("8833", state)
    for row in f8833.get("rows", []):
        print(f"  Box 2 Country:     {row['box_2_treaty_country']}")
        print(f"  Box 3 Article:     {row['box_3_treaty_article']}")
        print(f"  Box 4 IRC override:{row['box_4_irc_provision_overridden']}")
        print(f"  Box 6 Exempted:    ${row['box_6_amount_exempted']:,.2f}")

    print("\nForm 843 (FICA refund claim):")
    f843 = compute_form("843", state)
    print(f"  Line 1 amount to refund: ${f843['line_1_amount_to_refund']:,.2f}")
    print(f"  Line 3 tax type:         {f843['line_3_tax_type']}")
    print(f"  Line 4 IRC section:      {f843['line_4_explanation_irc_section']}")
    print(f"  Line 7 explanation: {f843['line_7_explanation_text']}")

    print("\nForm IT-203 (NY nonresident):")
    it203 = compute_form("IT-203", state)
    for k in (
        "line_1_federal_agi", "line_21_treaty_addback", "line_31_ny_agi",
        "line_33_standard_deduction", "line_37_ny_taxable_income",
        "line_38_ny_tax_resident_basis", "line_45_income_percentage",
        "line_46_apportioned_ny_tax", "line_50_nyc_resident_tax",
        "line_60_total_ny_state_local_tax", "line_62_ny_withholding",
        "line_63_nyc_withholding", "line_68_overpaid_refund", "line_70_amount_owed",
    ):
        if k in it203:
            print(f"  {k:<32} = {it203[k]!r}")

    # ------------------------------------------------------------------
    _hr("STAGE 7 — Audit trail (proof every layer ran)")
    # ------------------------------------------------------------------
    for entry in state.audit_trail:
        print(f"  {entry['layer']:<5} {entry['function']:<48}  {entry['rationale']}")

    # ------------------------------------------------------------------
    _hr("FINAL RESULTS SUMMARY")
    # ------------------------------------------------------------------
    print(f"Federal refund:        ${-state.tax.refund_or_owed:>10,.2f}")
    print(f"FICA refund (843):     ${fica_total:>10,.2f}")
    print(f"NY refund:             ${-state.ny.ny_refund_or_owed:>10,.2f}")
    total = -state.tax.refund_or_owed + fica_total - state.ny.ny_refund_or_owed
    print(f"TOTAL recovered:       ${total:>10,.2f}")
    print(f"Forms in mailing pkg:  {', '.join(state.forms_required + ['1040-NR', 'Schedule-OI', '8843'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
