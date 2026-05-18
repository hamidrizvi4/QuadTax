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


class TestScheduleNEC:
    def test_no_fdap_yields_empty_money_fields(self):
        state = _build_china_art20c_state()  # no FDAP for this filer
        m = compute("Schedule-NEC", state)
        assert m["line_15c_total_30"] == ""
        assert m["line_12_scholarship_14"] == ""
        assert m["line_16_tax_total"] == ""

    def test_with_fdap_routes_to_correct_column(self):
        state = _build_china_art20c_state()
        state.income.fdap_taxable_total = 5000.0
        state.tax.fdap_tax_liability = 700.0
        m = compute("Schedule-NEC", state)
        # F-1 → 14% column gets the scholarship.
        assert m["line_12_scholarship_14"] == "5000"
        assert m["line_16_tax_total"] == "700"


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
        assert m["part_III_relevant"] is True
        assert m["part_III_line_11_years_in_exempt_status"] == 2
        assert m["part_IV_relevant"] is False


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


class TestFormW7:
    def test_reason_code_a_when_treaty_claim(self):
        state = _build_china_art20c_state()
        m = compute("W-7", state)
        assert m["reason_code"] == "a"
        assert m["passport_number"] == "E12345678"
        assert m["treaty_country_when_reason_a"] == "CN"


class TestForm6251:
    def test_no_amt_when_state_amt_dict_absent(self):
        state = _build_china_art20c_state()
        m = compute("6251", state)
        assert m["line_11_amt_owed"] == ""
        assert m["_binds"] is False


class TestForm2210:
    def test_default_safe_harbor(self):
        state = _build_china_art20c_state()
        m = compute("2210", state)
        assert m["_safe_harbor_met"] is True
        assert m["line_17_total_penalty"] == ""
