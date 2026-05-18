"""Golden-fixture scenario data for the validation suite.

Each scenario is a self-contained dict describing:

    * ``name`` — short identifier
    * ``description`` — what the scenario tests
    * ``mcq`` — the answers handed to TaxEngine.run_full_pipeline
    * ``ocr`` — strings handed in for I-94 / W-2 / 1042-S (just dummies; the
      LLM mocks below produce the real numbers)
    * ``mocked_llm`` — dict mapping response_format class → parsed payload
    * ``expected`` — assertions to evaluate against the final state
    * ``required_forms`` — forms that MUST appear in state.forms_required
    * ``forbidden_forms`` — forms that MUST NOT appear

Expected values are *hand-computed* against the IRS rules (Pub 519 + Pub 901 +
TY2025 brackets) so a regression in the engine math fails this test.
"""

from __future__ import annotations

from typing import Any, Dict, List


SCENARIOS: List[Dict[str, Any]] = [
    # =================================================================
    # 1. China F-1 year 3, $25k W-2 — Art 20(c) caps at $5k, $20k taxed
    # =================================================================
    {
        "name": "cn_f1_3yr_oncampus",
        "description": "China F-1 year 3 with $25k on-campus wages.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2023,  # year 3 = 2025-2023+1
            "tax_residence_country": "CN",
            "income_description": "On-campus library worker",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 320,
                "days_minus_1": 200,
                "days_minus_2": 50,
            },
            "W2Data": {
                "box_1_wages": 25000.0,
                "box_2_fed_withholding": 3750.0,
                "box_3_ss_wages": 25000.0,
                "box_4_ss_withheld": 1550.0,
                "box_5_medicare_wages": 25000.0,
                "box_6_medicare_withheld": 362.5,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            "residency.status": "nonresident_alien",
            "residency.is_exempt_individual": True,
            "residency.years_in_exempt_status": 3,
            "treaty.country": "CN",
            "treaty.article_number": "20(c)",
            "treaty.exempt_amount_applied": 5000.0,
            # $20,000 taxable: 10% on first $11,925 + 12% on remaining $8,075 = $1,192.50 + $969 = $2,161.50 → $2,162
            "tax.eci_tax_liability": 2162.0,
            "tax.total_tax_liability": 2162.0,
            "tax.refund_or_owed": -1588.0,  # 2162 - 3750
            "fica.is_exempt": True,
            "fica.incorrect_ss_withheld": 1550.0,
            "fica.requires_form_843": True,
        },
        "required_forms": ["8833", "843"],
        "forbidden_forms": [],
    },
    # =================================================================
    # 2. China J-1 researcher year 2, $50k — Art 19 exempts all $50k
    # =================================================================
    {
        "name": "cn_j1_research_2yr",
        "description": "China J-1 researcher year 2 with $50k university stipend — Art 19 fully exempts.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "J-1",
            "first_us_arrival_year": 2024,
            "tax_residence_country": "CN",
            "income_description": "Postdoctoral researcher at MIT",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 365,
                "days_minus_1": 200,
                "days_minus_2": 0,
            },
            "W2Data": {
                "box_1_wages": 50000.0,
                "box_2_fed_withholding": 7500.0,
                "box_3_ss_wages": 50000.0,
                "box_4_ss_withheld": 3100.0,
                "box_5_medicare_wages": 50000.0,
                "box_6_medicare_withheld": 725.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "teaching_research"},
        },
        "expected": {
            "treaty.country": "CN",
            "treaty.article_number": "19",
            "treaty.exempt_amount_applied": 50000.0,
            "tax.eci_tax_liability": 0.0,
            "tax.total_tax_liability": 0.0,
            "tax.refund_or_owed": -7500.0,
        },
        "required_forms": ["8833"],
        "forbidden_forms": [],
    },
    # =================================================================
    # 3. India F-1 year 4, $20k — Art 21(2) gives single std deduction $15k
    # =================================================================
    {
        "name": "in_f1_4yr_standard_deduction",
        "description": "India F-1 year 4 with $20k wages — Art 21(2) standard deduction equivalent.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2022,
            "tax_residence_country": "IN",
            "income_description": "Campus job",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 300,
                "days_minus_1": 250,
                "days_minus_2": 100,
            },
            "W2Data": {
                "box_1_wages": 20000.0,
                "box_2_fed_withholding": 2500.0,
                "box_3_ss_wages": 20000.0,
                "box_4_ss_withheld": 1240.0,
                "box_5_medicare_wages": 20000.0,
                "box_6_medicare_withheld": 290.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            "treaty.country": "IN",
            "treaty.article_number": "21(2)",
            # After applying $15k single std deduction to $20k wages → $5,000 taxable
            # 10% on $5,000 = $500
            "tax.eci_tax_liability": 500.0,
            "tax.total_tax_liability": 500.0,
            "tax.refund_or_owed": -2000.0,  # 500 - 2500
        },
        "required_forms": ["8833"],
        "forbidden_forms": [],
    },
    # =================================================================
    # 4. Korea F-1 year 2, $10k — Art 21(1) $2,000 exempt
    # =================================================================
    {
        "name": "kr_f1_2yr",
        "description": "Korea F-1 year 2 with $10k wages — Art 21(1) $2,000 exempt.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2024,
            "tax_residence_country": "KR",
            "income_description": "Lab assistant",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 300,
                "days_minus_1": 250,
                "days_minus_2": 0,
            },
            "W2Data": {
                "box_1_wages": 10000.0,
                "box_2_fed_withholding": 1000.0,
                "box_3_ss_wages": 10000.0,
                "box_4_ss_withheld": 620.0,
                "box_5_medicare_wages": 10000.0,
                "box_6_medicare_withheld": 145.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            "treaty.country": "KR",
            "treaty.article_number": "21(1)",
            "treaty.exempt_amount_applied": 2000.0,
            # $8,000 taxable at 10% = $800
            "tax.eci_tax_liability": 800.0,
            "tax.total_tax_liability": 800.0,
            "tax.refund_or_owed": -200.0,
        },
        "required_forms": ["8833", "843"],
        "forbidden_forms": [],
    },
    # =================================================================
    # 5. Germany F-1 year 3, $40k — Art 20(4) $9k exempt
    # =================================================================
    {
        "name": "de_f1_3yr_9k_cap",
        "description": "Germany F-1 year 3 with $40k wages — Art 20(4) $9k exempt.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2023,
            "tax_residence_country": "DE",
            "income_description": "Research assistant",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 365,
                "days_minus_1": 300,
                "days_minus_2": 100,
            },
            "W2Data": {
                "box_1_wages": 40000.0,
                "box_2_fed_withholding": 5000.0,
                "box_3_ss_wages": 40000.0,
                "box_4_ss_withheld": 2480.0,
                "box_5_medicare_wages": 40000.0,
                "box_6_medicare_withheld": 580.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            "treaty.country": "DE",
            "treaty.article_number": "20(4)",
            "treaty.exempt_amount_applied": 9000.0,
            # $31,000 taxable: 10% × $11,925 + 12% × $19,075 = $1,192.50 + $2,289 = $3,481.50 → $3,482
            "tax.eci_tax_liability": 3482.0,
            "tax.refund_or_owed": -1518.0,
        },
        "required_forms": ["8833", "843"],
        "forbidden_forms": [],
    },
    # =================================================================
    # 6. UK F-1 year 1 with foreign remittance — Art 20 foreign-source only
    # =================================================================
    {
        "name": "gb_f1_us_wages_not_exempt",
        "description": "UK F-1 year 1 with $20k US-source wages — UK Art 20A does NOT exempt US-source.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2025,
            "tax_residence_country": "GB",
            "income_description": "On-campus job",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 200,
                "days_minus_1": 0,
                "days_minus_2": 0,
            },
            "W2Data": {
                "box_1_wages": 20000.0,
                "box_2_fed_withholding": 2400.0,
                "box_3_ss_wages": 20000.0,
                "box_4_ss_withheld": 1240.0,
                "box_5_medicare_wages": 20000.0,
                "box_6_medicare_withheld": 290.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            # UK treaty has foreign_source_remittance article but the LLM
            # mapped "student_personal_services" which is not in the UK file.
            "treaty.is_eligible": False,
            "treaty.exempt_amount_applied": 0.0,
            # $20,000 taxable at NRA single brackets: 10% × $11,925 + 12% × $8,075 = $1,192.50 + $969 = $2,161.50 → $2,162
            "tax.eci_tax_liability": 2162.0,
        },
        "required_forms": [],
        "forbidden_forms": ["8833"],
    },
    # =================================================================
    # 7. China F-1 year 6 (now resident alien) — saving clause preserves 20(c)
    # =================================================================
    {
        "name": "cn_f1_6yr_resident_alien",
        "description": "China F-1 year 6 — became RA under SPT but saving clause preserves Art 20(c).",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2020,  # year 6 = 2025-2020+1
            "tax_residence_country": "CN",
            "income_description": "Graduate teaching assistant",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 365,
                "days_minus_1": 365,
                "days_minus_2": 365,
            },
            "W2Data": {
                "box_1_wages": 30000.0,
                "box_2_fed_withholding": 4500.0,
                "box_3_ss_wages": 30000.0,
                "box_4_ss_withheld": 1860.0,
                "box_5_medicare_wages": 30000.0,
                "box_6_medicare_withheld": 435.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            # 5-year exempt window has closed; SPT met → resident alien
            "residency.is_exempt_individual": False,
            "residency.status": "resident_alien",
            # Saving-clause exception preserves China 20(c) → $5k still exempt
            "treaty.article_number": "20(c)",
            "treaty.exempt_amount_applied": 5000.0,
        },
        "required_forms": ["8833"],
        # No 843 — filer is now resident alien, FICA correctly owed
        "forbidden_forms": ["843"],
    },
    # =================================================================
    # 8. H-1B full year, no treaty — straight NRA-single brackets, FICA owed
    # =================================================================
    {
        "name": "noTreaty_h1b_full_yr",
        "description": "H-1B all year, no student treaty applies. SPT met → RA on $80k wages.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "H-1B",
            "first_us_arrival_year": 2020,
            "tax_residence_country": "BR",  # Brazil — no US treaty
            "income_description": "Software engineer",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 365,
                "days_minus_1": 365,
                "days_minus_2": 365,
            },
            "W2Data": {
                "box_1_wages": 80000.0,
                "box_2_fed_withholding": 12000.0,
                "box_3_ss_wages": 80000.0,
                "box_4_ss_withheld": 4960.0,
                "box_5_medicare_wages": 80000.0,
                "box_6_medicare_withheld": 1160.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "none"},
        },
        "expected": {
            "residency.status": "resident_alien",
            "treaty.is_eligible": False,
            # 2025 single brackets on $80,000:
            #   10% × $11,925         = $1,192.50
            #   12% × $36,550         = $4,386.00
            #   22% × $31,525         = $6,935.50
            #   Total                 = $12,514
            "tax.eci_tax_liability": 12514.0,
            "tax.refund_or_owed": 514.0,  # $12,514 owed − $12,000 withheld
            # No FICA refund — H-1B never had the exemption.
            "fica.requires_form_843": False,
        },
        "required_forms": [],
        "forbidden_forms": ["8833", "843"],
    },
    # =================================================================
    # 9. F-1 with $0 income — only 8843, no 1040-NR computation
    # =================================================================
    {
        "name": "f1_zero_income_8843_only",
        "description": "F-1 year 2 with no income — only 8843 required.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2024,
            "tax_residence_country": "CN",
            "income_description": "Full scholarship for tuition",
            "requires_services": False,
            "is_qualified_expense": True,
        },
        "ocr": {"i94": "dummy", "w2s": [], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 365,
                "days_minus_1": 200,
                "days_minus_2": 0,
            },
            "TreatyCategoryMapping": {"mapped_category": "scholarship_fellowship"},
        },
        "expected": {
            "residency.is_exempt_individual": True,
            "tax.total_tax_liability": 0.0,
            "tax.refund_or_owed": 0.0,
            "fica.requires_form_843": False,
        },
        "required_forms": [],
        "forbidden_forms": ["843"],
    },
    # =================================================================
    # 10. Pakistan F-1 year 3, $20k wages + $400 bank interest (Code 36 excluded)
    # =================================================================
    {
        "name": "pk_f1_3yr_with_bank_interest",
        "description": "Pakistan F-1 year 3 — Art XIII(1) $5k wage exempt + Code 36 bank interest excluded.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2023,
            "tax_residence_country": "PK",
            "income_description": "Library job",
            "requires_services": True,
            "is_qualified_expense": False,
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": ["dummy"]},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 365,
                "days_minus_1": 365,
                "days_minus_2": 200,
            },
            "W2Data": {
                "box_1_wages": 20000.0,
                "box_2_fed_withholding": 2200.0,
                "box_3_ss_wages": 20000.0,
                "box_4_ss_withheld": 1240.0,
                "box_5_medicare_wages": 20000.0,
                "box_6_medicare_withheld": 290.0,
            },
            "Form1042SData": {
                "box_1_income_code": 36,  # Bank deposit interest — excluded
                "box_2_gross_income": 400.0,
                "box_3a_exemption_rate": 0.0,
                "box_3b_exemption_code": "00",
                "box_7a_fed_withheld": 0.0,
                "chapter_indicator": 3,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            "treaty.country": "PK",
            "treaty.article_number": "XIII(1)",
            "treaty.exempt_amount_applied": 5000.0,
            # Code 36 (bank interest) lands in the EXCLUDED bucket — taxable
            # amount is zero by definition, so total_1042s_gross stays 400 but
            # fdap_taxable_total stays 0.
            "income.total_1042s_gross": 400.0,
            "income.fdap_taxable_total": 0.0,
            # $15,000 taxable at 10% × $11,925 + 12% × $3,075 = $1,192.50 + $369 = $1,561.50 → $1,562
            "tax.eci_tax_liability": 1562.0,
            "fica.requires_form_843": True,
        },
        "required_forms": ["8833", "843"],
        "forbidden_forms": [],
    },
    # =================================================================
    # 11. NY F-1 in dorm (Knight case) — NY nonresident
    # =================================================================
    {
        "name": "ny_f1_dorm_nonresident",
        "description": "NYU F-1 in dorm year-round — NY nonresident under Knight; $5k treaty addback.",
        "mcq": {
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
                "nyc_address": False,
            },
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 330,
                "days_minus_1": 200,
                "days_minus_2": 0,
            },
            "W2Data": {
                "box_1_wages": 30000.0,
                "box_2_fed_withholding": 4500.0,
                "box_3_ss_wages": 30000.0,
                "box_4_ss_withheld": 1860.0,
                "box_5_medicare_wages": 30000.0,
                "box_6_medicare_withheld": 435.0,
                "box_17_state_income_tax": 1200.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            "ny.residency_status": "nonresident",
            "ny.ny_treaty_addback": 5000.0,
            "ny.ny_agi": 30000.0,
            "ny.ny_standard_deduction": 8000.0,
            "ny.ny_taxable_income": 22000.0,
            "ny.nyc_tax": 0.0,
        },
        "required_forms": ["8833", "843", "IT-203", "IT-203-B"],
        "forbidden_forms": [],
    },
    # =================================================================
    # 12. NY F-1 statutory resident — Brooklyn apartment year-round, >183 days
    # =================================================================
    {
        "name": "ny_f1_statutory_resident",
        "description": "F-1 with year-round Brooklyn apartment + 200 days in NY → NY statutory resident.",
        "mcq": {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2024,
            "tax_residence_country": "CN",
            "income_description": "Dining hall worker",
            "requires_services": True,
            "is_qualified_expense": False,
            "ny_intake": {
                "days_in_ny": 200,
                "has_permanent_abode_in_ny": True,
                "abode_months_in_year": 12,
                "is_student_dorm": False,  # Real apartment, not dorm
                "domiciled_in_ny": False,
                "ny_work_days": 200,
                "total_work_days": 200,
                "employer_in_ny": True,
                "institution_1042s_in_ny": True,
                "nyc_address": True,  # Brooklyn → NYC resident
            },
        },
        "ocr": {"i94": "dummy", "w2s": ["dummy"], "f1042s": []},
        "mocked_llm": {
            "I94DayCountParams": {
                "days_current_year": 200,
                "days_minus_1": 100,
                "days_minus_2": 0,
            },
            "W2Data": {
                "box_1_wages": 30000.0,
                "box_2_fed_withholding": 4500.0,
                "box_3_ss_wages": 30000.0,
                "box_4_ss_withheld": 1860.0,
                "box_5_medicare_wages": 30000.0,
                "box_6_medicare_withheld": 435.0,
                "box_17_state_income_tax": 1200.0,
                "box_19_local_income_tax": 600.0,
            },
            "TreatyCategoryMapping": {"mapped_category": "student_personal_services"},
        },
        "expected": {
            # F-1 federal NRA preserved (exempt under §7701(b)(5)).
            "residency.status": "nonresident_alien",
            # But NY statutory residency applies — files IT-201 (resident).
            "ny.residency_status": "resident",
            "ny.nyc_resident": True,
        },
        "required_forms": ["8833", "843", "IT-201"],
        "forbidden_forms": ["IT-203"],
    },
]


SCENARIOS_BY_NAME = {s["name"]: s for s in SCENARIOS}
