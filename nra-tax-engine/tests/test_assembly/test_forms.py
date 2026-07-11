"""Tests for the per-form field-map populators (Phase 3)."""

from src.assembly.forms import FORM_REGISTRY, compute
from src.orchestrator.state import ReturnStateObject


def _build_china_art20c_state() -> ReturnStateObject:
    """Build the canonical Phase 3 acceptance fixture."""
    state = ReturnStateObject(tax_year=2025)

    state.identity.first_name = "Ming"
    state.identity.last_name = "Chen"
    state.identity.ssn = ""
    state.identity.itin = "912345678"
    state.identity.us_address_line1 = "123 Beacon St Apt 4"
    state.identity.us_city = "Boston"
    state.identity.us_state = "MA"
    state.identity.us_zip = "02115"
    state.identity.foreign_country = "CN"
    state.identity.country_of_citizenship = "CN"
    state.identity.country_of_tax_residence = "CN"
    state.identity.passport_number = "E12345678"
    state.identity.passport_country = "CN"
    state.identity.occupation = "Graduate Student"
    state.identity.filing_status = "single"

    state.residency.status = "nonresident_alien"
    state.residency.exempt_visa_type = "F-1"
    state.residency.years_in_exempt_status = 2
    state.residency.spt_days_current_year = 300
    state.residency.days_present_current_year = 300
    state.residency.days_present_year_minus_1 = 365
    state.residency.days_present_year_minus_2 = 0
    state.residency.is_exempt_individual = True

    state.income.total_w2_wages = 30000.0
    state.income.eci_taxable_total = 30000.0
    state.income.fdap_taxable_total = 0.0

    state.treaty.is_eligible = True
    state.treaty.country = "CN"
    state.treaty.article_number = "20(c)"
    state.treaty.exempt_amount_applied = 5000.0
    state.treaty.applied_to_category = "student_personal_services"
    state.treaty.requires_form_8833 = True
    state.treaty.applied_benefits = [
        {
            "country_iso2": "CN",
            "country_name": "China (People's Republic of)",
            "article_id": "20(c)",
            "category": "student_personal_services",
            "exempt_amount": 5000.0,
            "rate_override": None,
            "applies_after_saving_clause": False,
            "requires_form_8833": True,
            "explanation": (
                "US-China treaty Article 20(c) (student_personal_services): "
                "exempts $5,000; annual cap $5,000; saving-clause exception applies."
            ),
        }
    ]

    state.fica.is_exempt = True
    state.fica.incorrect_ss_withheld = 1860.0
    state.fica.incorrect_medicare_withheld = 435.0
    state.fica.requires_form_843 = True

    state.tax.eci_tax_liability = 2762.0
    state.tax.fdap_tax_liability = 0.0
    state.tax.total_tax_liability = 2762.0
    state.tax.total_withholding_credits = 4500.0
    state.tax.refund_or_owed = -1738.0

    state.withholding_report = {
        "federal_w2": 4500.0,
        "federal_1042s_ch3": 0.0,
        "federal_1042s_ch4": 0.0,
        "federal_1099": 0.0,
        "federal_estimated_payments": 0.0,
        "federal_total": 4500.0,
        "ss_withheld_w2": 1860.0,
        "medicare_withheld_w2": 435.0,
        "state_income_tax_w2": 1200.0,
        "local_income_tax_w2": 600.0,
        "sources_seen": ["W-2"],
    }
    state.forms_required = ["8833", "843"]
    state.ready_for_assembly = True
    return state


class TestRegistry:
    def test_every_registered_form_dispatches(self):
        state = _build_china_art20c_state()
        for form_name in FORM_REGISTRY:
            result = compute(form_name, state)
            assert isinstance(result, dict), f"{form_name} did not return a dict"


class TestForm1040NR:
    def test_identity_and_money_lines(self):
        state = _build_china_art20c_state()
        m = compute("1040-NR", state)
        assert m["last_name"] == "Chen"
        assert m["identifying_number"] == "912345678"
        assert m["us_state"] == "MA"
        assert m["line_1a_wages"] == "30000"
        assert m["line_1k_treaty_exempt_wages"] == "5000"
        assert m["line_16_tax"] == "2762"
        assert m["line_24_total_tax"] == "2762"
        assert m["line_25a_w2_withholding"] == "4500"
        assert m["line_33_refund"] == "1738"
        assert m["line_37_owed"] == ""  # zero amount → empty per IRS convention
        assert m["signature_occupation"] == "Graduate Student"
        # Filing status checkboxes
        assert m["filing_status_single"] is True
        assert m["filing_status_mfs"] is False
        # Direct deposit not requested by default -> banking lines blank.
        assert m["line_35b_routing_number"] == ""
        assert m["line_35c_account_type_checking"] is False
        assert m["line_35d_account_number"] == ""

    def test_direct_deposit_fills_banking_lines(self):
        state = _build_china_art20c_state()
        state.tax.direct_deposit = True
        state.tax.routing_number = "021000021"
        state.tax.account_number = "000123456789"
        state.tax.account_type = "checking"
        m = compute("1040-NR", state)
        assert m["line_35b_routing_number"] == "021000021"
        assert m["line_35d_account_number"] == "000123456789"
        assert m["line_35c_account_type_checking"] is True
        assert m["line_35c_account_type_savings"] is False

    def test_direct_deposit_savings_account(self):
        state = _build_china_art20c_state()
        state.tax.direct_deposit = True
        state.tax.account_type = "savings"
        m = compute("1040-NR", state)
        assert m["line_35c_account_type_checking"] is False
        assert m["line_35c_account_type_savings"] is True


class TestScheduleOI:
    def test_treaty_table_populated(self):
        state = _build_china_art20c_state()
        m = compute("Schedule-OI", state)
        rows = m["item_L_treaty_rows"]
        assert len(rows) == 1
        assert rows[0]["country"] == "China (People's Republic of)"
        assert rows[0]["article"] == "20(c)"
        assert rows[0]["amount_this_year"] == 5000.0
        assert m["item_A_country_citizenship"] == "CN"
        assert m["item_C_visa_type"] == "F-1"
        assert m["item_G_days_current_year"] == 300
        assert m["item_G_days_year_minus_1"] == 365
        assert m["item_G_days_year_minus_2"] == 0

    def test_item_h_reflects_extras_filed_previous_return(self):
        state = _build_china_art20c_state()
        state.extras.filed_previous_federal_return = True
        m = compute("Schedule-OI", state)
        assert m["item_H_filed_1040_prior_year"] is True

    def test_elections_reflected_when_force_assembled(self):
        """Items I/K/M mirror state.elections — only reachable in practice
        via force_assembly=True since the human-review gate blocks assembly
        whenever any of these is set."""
        state = _build_china_art20c_state()
        state.elections.section_6013g_election = True
        state.elections.section_871d_election = True
        state.elections.large_foreign_gifts_over_100k = True
        state.elections.closer_connection_exception_claimed = True
        m = compute("Schedule-OI", state)
        assert m["item_I_6013_election"] is True
        assert m["item_J_871d_election"] is True
        assert m["item_K_large_foreign_gifts"] is True
        assert m["item_M_closer_connection"] is True

    def test_prior_year_treaty_claim_on_first_row(self):
        state = _build_china_art20c_state()
        state.treaty.prior_year_treaty_claim_total = 4500.0
        m = compute("Schedule-OI", state)
        assert m["item_L_treaty_rows"][0]["amount_prior_years"] == 4500.0

    def test_prior_year_resident_status_reflected(self):
        state = _build_china_art20c_state()
        state.residency.prior_year_residency_status = "resident_alien"
        m = compute("Schedule-OI", state)
        assert m["item_E_prior_year_resident"] is True


class TestScheduleNEC:
    def test_no_fdap_yields_empty_money_fields(self):
        state = _build_china_art20c_state()  # no FDAP for this filer
        m = compute("Schedule-NEC", state)
        assert m["line_14_tax_30"] == ""
        assert m["line_12_scholarship_other_rate"] == ""
        assert m["line_15_tax_total"] == ""

    def test_with_fdap_routes_to_correct_column(self):
        state = _build_china_art20c_state()
        state.income.fdap_taxable_total = 5000.0
        state.tax.fdap_tax_liability = 700.0
        m = compute("Schedule-NEC", state)
        # F-1 → this form has no dedicated 14% column, so it lands in "Other rate".
        assert m["line_12_scholarship_other_rate"] == "5000"
        assert m["line_13_subtotal_other_rate"] == "5000"
        assert m["line_14_tax_other_rate"] == "5000"
        assert m["line_15_tax_total"] == "700"


class TestScheduleA:
    def test_disallowed_items_surfaced(self):
        state = _build_china_art20c_state()
        state.sch_a = {
            "state_local_income_tax": 1800.0,
            "salt_cap_bite": 0.0,
            "charitable_cash": 200.0,
            "charitable_noncash": 0.0,
            "casualty_disaster_loss": 0.0,
            "other_itemized": 0.0,
            "total": 2000.0,
            "disallowed_items": [
                "Mortgage interest ($12,000) is not deductible on Form 1040-NR Schedule A."
            ],
        }
        m = compute("Schedule-A", state)
        assert m["line_1a_state_local_income_tax"] == "1800"
        assert m["line_8_total_itemized"] == "2000"
        assert m["_disallowed_items_warnings"][0].startswith("Mortgage")


class TestForm8843:
    def test_part_iii_populated_for_f1(self):
        state = _build_china_art20c_state()
        m = compute("8843", state)
        assert m["part_I_name"] == "Ming Chen"
        assert m["part_I_visa_type_current"] == "F-1"
        assert m["_part_III_relevant"] is True
        assert m["_part_IV_relevant"] is False

    def test_line_4a_uses_raw_presence_not_spt_adjusted(self):
        """spt_days_current_year is 0 for a fully-exempt filer; line 4a must
        still report actual physical presence, not the SPT-purposes count."""
        state = _build_china_art20c_state()
        state.residency.spt_days_current_year = 0  # fully excluded as exempt
        state.residency.days_present_current_year = 300
        state.residency.days_present_year_minus_1 = 200
        state.residency.days_present_year_minus_2 = 50
        m = compute("8843", state)
        assert m["part_I_days_current_year"] == 300
        assert m["part_I_days_year_minus_1"] == 200
        assert m["part_I_days_year_minus_2"] == 50
        assert m["part_I_days_excluded_for_spt"] == 300

    def test_line_11_visa_grid_reflects_first_exempt_year(self):
        """tax_year=2025, years_in_exempt_status=2 -> first exempt year 2024,
        which is the most recent slot (yr_minus_1) in the 2019-2024 window."""
        state = _build_china_art20c_state()
        m = compute("8843", state)
        assert m["part_III_line_11_visa_yr_minus_1"] == "F-1"  # 2024
        assert m["part_III_line_11_visa_yr_minus_2"] == ""  # 2023, pre-arrival
        assert m["part_III_line_11_visa_yr_minus_6"] == ""  # 2019, pre-arrival

    def test_line_12_exempt_more_than_5_years(self):
        state = _build_china_art20c_state()
        state.residency.years_in_exempt_status = 2
        m = compute("8843", state)
        assert m["part_III_line_12_exempt_more_than_5_years"] is False

        state.residency.years_in_exempt_status = 6
        m = compute("8843", state)
        assert m["part_III_line_12_exempt_more_than_5_years"] is True


class TestForm8833:
    def test_one_row_per_qualifying_benefit(self):
        state = _build_china_art20c_state()
        m = compute("8833", state)
        assert m["count"] == 1
        row = m["rows"][0]
        assert row["box_2_treaty_country"] == "China (People's Republic of)"
        assert row["box_3_treaty_article"] == "20(c)"
        assert row["box_6_amount_exempted"] == 5000.0
        assert "§871(b)" in row["box_4_irc_provision_overridden"]


class TestForm843:
    def test_explanation_and_amounts(self):
        state = _build_china_art20c_state()
        m = compute("843", state)
        assert m["line_1_amount_to_refund"] == 2295.0  # 1860 + 435
        assert m["line_3_tax_type"] == "FICA"
        assert "§3121(b)(19)" in m["line_4_explanation_irc_section"]
        assert "F-1" in m["line_7_explanation_text"]

    def test_explanation_does_not_assert_unconfirmed_employer_refusal(self):
        """Without employer_attempted_refund confirmed, the explanation must
        not claim the employer was asked — that would misstate a fact on a
        document filed under penalty of perjury."""
        state = _build_china_art20c_state()
        state.fica.employer_attempted_refund = False
        state.fica.has_form_8316 = False
        m = compute("843", state)
        text = m["line_7_explanation_text"]
        assert "requested a refund from the employer and did not receive" not in text
        assert "should request a refund from the employer" in text

    def test_explanation_reflects_confirmed_employer_attempt(self):
        state = _build_china_art20c_state()
        state.fica.employer_attempted_refund = True
        state.fica.has_form_8316 = False
        m = compute("843", state)
        assert "requested a refund from the employer and did not receive" in m["line_7_explanation_text"]

    def test_explanation_reflects_employer_written_statement(self):
        state = _build_china_art20c_state()
        state.fica.employer_attempted_refund = True
        state.fica.has_form_8316 = True
        m = compute("843", state)
        assert "confirmed in writing that it will not issue a refund" in m["line_7_explanation_text"]


class TestFormW7:
    def test_reason_code_a_when_treaty_claim(self):
        state = _build_china_art20c_state()
        m = compute("W-7", state)
        assert m["reason_code"] == "a"
        assert m["passport_number"] == "E12345678"
        assert m["treaty_country_when_reason_a"] == "CN"
        # Exactly one of the 8 reason checkboxes should be True.
        assert m["reason_a"] is True
        for letter in "bcdefgh":
            assert m[f"reason_{letter}"] is False
        assert m["application_type_new"] is True
        assert m["application_type_renewal"] is False

    def test_reason_code_f_default_checks_only_f(self):
        state = _build_china_art20c_state()
        state.treaty.applied_benefits = []  # no 8833 requirement -> falls to default "f"
        m = compute("W-7", state)
        assert m["reason_code"] == "f"
        assert m["reason_f"] is True
        for letter in "abcdegh":
            assert m[f"reason_{letter}"] is False

    def test_renewal_flag_reflects_itin_eligibility(self):
        state = _build_china_art20c_state()
        state.itin_eligibility = {"is_renewal": True}
        m = compute("W-7", state)
        assert m["application_type_new"] is False
        assert m["application_type_renewal"] is True


class TestForm6251:
    def test_no_amt_when_state_amt_dict_absent(self):
        state = _build_china_art20c_state()
        m = compute("6251", state)
        assert m["line_11_amt_owed"] == ""
        assert m["_binds"] is False

    def test_line_1_uses_taxable_income_not_tax_liability(self):
        """Regression test: line 1 was reading eci_tax_liability (a computed
        tax dollar amount) instead of taxable_income — the author's own
        '# placeholder' comment confirmed this was known-wrong."""
        state = _build_china_art20c_state()
        state.tax.taxable_income = 25000.0
        state.tax.eci_tax_liability = 2762.0  # deliberately different
        m = compute("6251", state)
        assert m["line_1_taxable_income"] == "25000"


class TestForm2210:
    def test_default_safe_harbor(self):
        state = _build_china_art20c_state()
        m = compute("2210", state)
        assert m["_safe_harbor_met"] is True
        assert m["line_17_total_penalty"] == ""


def _build_india_art21_2_state() -> ReturnStateObject:
    """India F-1: Art 21(2) standard-deduction equivalent ($15k single, TY2025).

    Regression fixture for the QA-caught form bugs — India's deduction is NOT a
    wage exemption, so line 1k and Schedule OI Item L must stay empty while
    line 12 (deduction) and line 15 (taxable income) carry the real figures.
    """
    state = ReturnStateObject(tax_year=2025)
    state.identity.first_name = "Arjun"
    state.identity.last_name = "Sharma"
    state.identity.itin = "998765432"
    state.identity.country_of_citizenship = "IN"
    state.identity.country_of_tax_residence = "IN"
    state.identity.filing_status = "single"
    state.residency.status = "nonresident_alien"
    state.residency.exempt_visa_type = "F-1"
    state.residency.years_in_exempt_status = 3
    state.residency.is_exempt_individual = True

    state.income.total_w2_wages = 28000.0
    state.income.eci_taxable_total = 28000.0

    # As produced by L4 for India: 21(2) benefit present, but excluded from
    # exempt_amount_applied (it's a deduction, not a wage exemption).
    state.treaty.is_eligible = True
    state.treaty.country = "IN"
    state.treaty.article_number = "21(2)"
    state.treaty.exempt_amount_applied = 0.0
    state.treaty.applied_to_category = "student_personal_services"
    state.treaty.requires_form_8833 = True
    state.treaty.applied_benefits = [
        {
            "country_iso2": "IN",
            "country_name": "India",
            "article_id": "21(2)",
            "category": "student_personal_services",
            "exempt_amount": 28000.0,  # phantom (uncapped) — must not surface on forms
            "rate_override": None,
            "applies_after_saving_clause": False,
            "requires_form_8833": True,
            "explanation": "India Article 21(2) standard-deduction equivalent.",
        }
    ]

    # As produced by L6.
    state.tax.agi = 28000.0
    state.tax.deduction_amount = 15000.0
    state.tax.deduction_type = "standard"
    state.tax.taxable_income = 13000.0
    state.tax.eci_tax_liability = 1322.0
    state.tax.total_tax_liability = 1322.0
    state.tax.total_withholding_credits = 4200.0
    state.tax.refund_or_owed = -2878.0
    return state


class TestIndiaForm1040NR:
    """Regression for the India Art 21(2) form-population bugs caught by QA."""

    def test_line_12_shows_standard_deduction(self):
        m = compute("1040-NR", _build_india_art21_2_state())
        assert m["line_12_deduction"] == "15000"

    def test_line_15_taxable_income_is_agi_minus_deduction(self):
        m = compute("1040-NR", _build_india_art21_2_state())
        assert m["line_11_agi"] == "28000"
        assert m["line_15_taxable_income"] == "13000"

    def test_line_1k_treaty_exempt_wages_is_empty(self):
        """India exempts NO wages — line 1k must be blank."""
        m = compute("1040-NR", _build_india_art21_2_state())
        assert m["line_1k_treaty_exempt_wages"] == ""

    def test_line_16_tax_and_refund(self):
        m = compute("1040-NR", _build_india_art21_2_state())
        assert m["line_16_tax"] == "1322"
        assert m["line_33_refund"] == "2878"

    def test_schedule_oi_item_l_excludes_india_21_2(self):
        """India 21(2) is a deduction, not exempt income — Item L must omit it."""
        m = compute("Schedule-OI", _build_india_art21_2_state())
        assert m["item_L_treaty_rows"] == []

    def test_form_8833_still_generated_for_india(self):
        """Disclosure is still filed even though the benefit is a deduction."""
        m = compute("8833", _build_india_art21_2_state())
        assert m["count"] == 1
        assert m["rows"][0]["box_2_treaty_country"] == "India"
        assert m["rows"][0]["box_3_treaty_article"] == "21(2)"


class TestFormIT203B:
    def test_workday_and_abode_fields_reflect_real_ny_state(self):
        """Regression test: these were hardcoded to 0/365 regardless of
        intake — NYAgent computes real allocation math from ny_work_days/
        total_work_days/abode_months_in_year but never wrote them back onto
        NYTaxState, so the form that displays them had nothing to read."""
        state = _build_china_art20c_state()
        state.ny.ny_work_days = 180
        state.ny.total_work_days = 200
        state.ny.abode_months_in_year = 9
        m = compute("IT-203-B", state)
        assert m["sched_A_ny_workdays"] == 180
        assert m["sched_A_total_workdays_in_year"] == 200
        assert m["sched_A_workdays_outside_ny"] == 20
        assert m["sched_B_months_maintained"] == 9

    def test_workday_outside_ny_never_negative(self):
        state = _build_china_art20c_state()
        state.ny.ny_work_days = 50
        state.ny.total_work_days = 0  # not yet populated
        m = compute("IT-203-B", state)
        assert m["sched_A_workdays_outside_ny"] == 0
