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

    state.tax.agi = 25000.0  # net_eci: $30,000 wages − $5,000 China Art 20(c) exemption
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
        # Line 1a must be NET of the $5,000 treaty exemption per IRS
        # instructions ("wages...exempt...under an income tax treaty
        # should not be reported on line 1a"), not the gross $30,000 W-2
        # figure — regression guard for a confirmed wrong-amount bug.
        assert m["line_1a_wages"] == "25000"
        assert m["line_1k_treaty_exempt_wages"] == "5000"
        # 1z = "Add lines 1a through 1h" — only 1a populated, so 1z == 1a.
        assert m["line_1z_total_wages_net"] == "25000"
        # Line 9 mirrors the authoritative AGI (line 10 adjustments unmodeled).
        assert m["line_9_total_income"] == "25000"
        assert m["line_11_agi"] == "25000"
        assert m["line_11b_agi"] == "25000"  # page-2 carry-forward of line 11a
        assert m["line_16_tax"] == "2762"
        # No AMT/FDAP in this fixture -> lines 17/23a/23d blank, not "0".
        assert m["line_17_sch2_amt"] == ""
        assert m["line_18_tax_and_amt"] == "2762"
        assert m["line_22_tax_after_credits"] == "2762"
        assert m["line_23a_fdap_tax"] == ""
        assert m["line_23d_addl_tax_subtotal"] == ""
        assert m["line_24_total_tax"] == "2762"
        assert m["line_25a_w2_withholding"] == "4500"
        assert m["line_25b_1099_withholding"] == ""
        assert m["line_25d_subtotal"] == "4500"
        assert m["line_25g_1042s_withholding"] == ""
        assert m["line_33_total_payments"] == "4500"
        assert m["line_34_overpaid"] == "1738"
        assert m["line_37_owed"] == ""  # zero amount → empty per IRS convention
        assert m["line_38_estimated_tax_penalty"] == ""
        # Line 8 ("Additional income from Schedule 1") has no state backing
        # and must never be fabricated by (mis)reusing FDAP income.
        assert "line_8_scholarship_taxable" not in m
        assert m["signature_occupation"] == "Graduate Student"
        # Filing status checkboxes
        assert m["filing_status_single"] is True
        assert m["filing_status_mfs"] is False
        # Direct deposit not requested by default -> banking lines blank.
        assert m["line_35b_routing_number"] == ""
        assert m["line_35c_account_type_checking"] is False
        assert m["line_35d_account_number"] == ""
        # Digital assets defaults to No.
        assert m["digital_assets_yes"] is False
        assert m["digital_assets_no"] is True

    def test_amt_flows_from_state_amt_dict_not_state_tax(self):
        """Regression guard: AMT lives on ``state.amt`` (a plain dict
        populated by AMTCalculator), not ``state.tax`` — the previous code
        read a nonexistent ``state.tax.amt_owed`` attribute via a ``hasattr``
        guard that was always False, so AMT silently never reached the
        1040-NR even when Form 6251 computed a real liability."""
        state = _build_china_art20c_state()
        state.amt = {"amti": 40000.0, "exemption": 30000.0, "amt_owed": 500.0, "binds": True}
        m = compute("1040-NR", state)
        assert m["line_17_sch2_amt"] == "500"
        assert m["line_18_tax_and_amt"] == "3262"  # 2762 (line 16) + 500 (line 17)
        assert m["line_22_tax_after_credits"] == "3262"
        assert m["line_24_total_tax"] == "3262"  # 2762 total_tax_liability + 500 AMT

    def test_fdap_tax_reported_on_line_23a_not_line_8(self):
        """Regression guard for a confirmed double-count bug: FDAP income is
        reported on Schedule NEC and must flow to 1040-NR line 23a (the
        Schedule-NEC tax line), never onto line 8 ("Additional income from
        Schedule 1") — a completely different, unrelated income category
        with no state backing in this engine."""
        state = _build_china_art20c_state()
        state.income.fdap_taxable_total = 5000.0
        state.tax.fdap_tax_liability = 700.0
        state.tax.total_tax_liability = 2762.0 + 700.0
        m = compute("1040-NR", state)
        assert m["line_23a_fdap_tax"] == "700"
        assert m["line_23d_addl_tax_subtotal"] == "700"
        assert "line_8_scholarship_taxable" not in m
        assert m["line_24_total_tax"] == "3462"

    def test_estimated_tax_penalty_flows_to_line_38(self):
        state = _build_china_art20c_state()
        state.estimated_tax_penalty = {"penalty_amount": 42.0, "safe_harbor_met": False}
        m = compute("1040-NR", state)
        assert m["line_38_estimated_tax_penalty"] == "42"

    def test_digital_assets_yes_when_extras_flag_set(self):
        state = _build_china_art20c_state()
        state.extras.had_digital_assets = True
        m = compute("1040-NR", state)
        assert m["digital_assets_yes"] is True
        assert m["digital_assets_no"] is False

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
        # Item E on the TY2025 AcroForm is visa type (was mislabeled "C" on
        # older Schedule OI revisions — see schedule_oi.py's field-letter map).
        assert m["item_E_visa_type"] == "F-1"
        # Item H is the 3-year day-count table (was mislabeled "G").
        assert m["item_H_days_current_year"] == 300
        assert m["item_H_days_year_minus_1"] == 365
        assert m["item_H_days_year_minus_2"] == 0
        # Header must repeat the filer's name/TIN, like every attached schedule.
        assert m["header_name"] == "Ming Chen"
        assert m["header_identifying_number"] == "912345678"

    def test_item_i_reflects_extras_filed_previous_return(self):
        """Item I (was mislabeled "H") is a real Yes/No checkbox *pair* on the
        AcroForm (c1_6[0]/c1_6[1] are independent fields, not radio-group
        kids) — a confident False must explicitly check the No box, not just
        leave both blank (indistinguishable from unanswered)."""
        state = _build_china_art20c_state()
        state.extras.filed_previous_federal_return = True
        m = compute("Schedule-OI", state)
        assert m["item_I_filed_1040_prior_year_yes"] is True
        assert m["item_I_filed_1040_prior_year_no"] is False

        state.extras.filed_previous_federal_return = False
        m = compute("Schedule-OI", state)
        assert m["item_I_filed_1040_prior_year_yes"] is False
        assert m["item_I_filed_1040_prior_year_no"] is True

    def test_item_i_prior_return_detail_filled_when_yes(self):
        state = _build_china_art20c_state()
        state.extras.filed_previous_federal_return = True
        state.extras.previous_return_year = 2023
        state.extras.previous_return_type = "1040-NR"
        m = compute("Schedule-OI", state)
        assert m["item_I_prior_return_year_and_form"] == "2023 1040-NR"

    def test_elections_reflected_when_force_assembled(self):
        """§871(d) (Item M1) is the only one of these five election flags
        with a live field on the current AcroForm — §6013, the >$100k
        foreign-gift disclosure, and the closer-connection exception have
        no Schedule OI field on the TY2025 revision at all (see module
        docstring) and are only reachable in practice via force_assembly=True
        since the human-review gate blocks assembly whenever any of these
        is set; they're still surfaced informationally for that review."""
        state = _build_china_art20c_state()
        state.elections.section_6013g_election = True
        state.elections.section_871d_election = True
        state.elections.large_foreign_gifts_over_100k = True
        state.elections.closer_connection_exception_claimed = True
        m = compute("Schedule-OI", state)
        assert m["item_M1_871d_election_first_year"] is True
        assert m["_election_6013_reported"] is True
        assert m["_large_foreign_gifts_reported"] is True
        assert m["_closer_connection_reported"] is True

    def test_prior_year_treaty_claim_on_first_displayed_row(self):
        state = _build_china_art20c_state()
        state.treaty.prior_year_treaty_claim_total = 4500.0
        m = compute("Schedule-OI", state)
        assert m["item_L_treaty_rows"][0]["amount_prior_years"] == 4500.0

    def test_prior_year_treaty_claim_skips_excluded_india_row(self):
        """If applied_benefits[0] is the excluded India 21(2) entry, the
        prior-year total must land on the first row that actually gets
        displayed (China), not silently disappear because index 0 in the
        unfiltered list was skipped."""
        state = _build_china_art20c_state()
        state.treaty.prior_year_treaty_claim_total = 4500.0
        state.treaty.applied_benefits = [
            {
                "country_iso2": "IN",
                "country_name": "India",
                "article_id": "21(2)",
                "category": "student_personal_services",
                "exempt_amount": 15000.0,
            },
        ] + state.treaty.applied_benefits
        m = compute("Schedule-OI", state)
        rows = m["item_L_treaty_rows"]
        assert len(rows) == 1
        assert rows[0]["country"] == "China (People's Republic of)"
        assert rows[0]["amount_prior_years"] == 4500.0

    def test_item_l_total_matches_1040nr_line_1k_wage_filter(self):
        """Item L's (e) Total must equal 1040-NR line 1k exactly — the IRS
        instructs filers to "enter this amount on line 1k... and nowhere
        else." A scholarship-category benefit belongs in the Item L table
        (for disclosure) but must NOT be counted in the (e) Total, since it
        never nets against Line 1a wages."""
        state = _build_china_art20c_state()
        state.treaty.applied_benefits = [
            {
                "country_iso2": "CN",
                "country_name": "China (People's Republic of)",
                "article_id": "20(c)",
                "category": "student_personal_services",
                "exempt_amount": 5000.0,
            },
            {
                "country_iso2": "CN",
                "country_name": "China (People's Republic of)",
                "article_id": "20(b)",
                "category": "scholarship_fellowship",
                "exempt_amount": 3000.0,
            },
        ]
        m = compute("Schedule-OI", state)
        assert len(m["item_L_treaty_rows"]) == 2
        assert m["item_L_total_exempt_amount"] == 5000.0
        oi_total = m["item_L_total_exempt_amount"]
        nr_line_1k = float(compute("1040-NR", state)["line_1k_treaty_exempt_wages"])
        assert oi_total == nr_line_1k

    def test_prior_year_resident_status_is_informational_only(self):
        """Pre-2022 Schedule OI had an Item E "were you a US resident in a
        prior year?" checkbox; the TY2025 revision's Item E is a different
        question (visa type) and no field anywhere asks this anymore, so
        this value is surfaced only for the JSON-fallback audit view
        (leading underscore -> never written to the real PDF)."""
        state = _build_china_art20c_state()
        state.residency.prior_year_residency_status = "resident_alien"
        m = compute("Schedule-OI", state)
        assert m["_prior_year_resident_status_reported"] is True


class TestScheduleNEC:
    def test_no_fdap_yields_empty_money_fields(self):
        state = _build_china_art20c_state()  # no FDAP for this filer
        m = compute("Schedule-NEC", state)
        assert m["line_14_tax_30"] == ""
        assert m["line_12_scholarship_other_rate"] == ""
        assert m["line_15_tax_total"] == ""
        assert m["line_12_other_specify"] == ""
        assert m["line_hdr_other_rate_pct"] == ""
        # Header must still be populated even when there's no FDAP to report.
        assert m["header_name"] == "Ming Chen"
        assert m["header_identifying_number"] == "912345678"

    def test_with_fdap_routes_to_correct_column(self):
        state = _build_china_art20c_state()
        state.income.fdap_taxable_total = 5000.0
        state.tax.fdap_tax_liability = 700.0
        m = compute("Schedule-NEC", state)
        # F-1 → this form has no dedicated 14% column, so it lands in "Other rate".
        assert m["line_12_scholarship_other_rate"] == "5000"
        assert m["line_13_subtotal_other_rate"] == "5000"
        # Regression guard: line 14 is "line 13 * rate of tax at top of the
        # column" — i.e. the TAX ($700 = $5,000 * 14%), not a repeat of the
        # line 13 income figure. An earlier version of this module wrote
        # "5000" here, which silently disagreed with line 15 (the sum of
        # line 14) and would have overstated the FDAP tax due 30-fold if a
        # preparer or the IRS actually multiplied line 13 by 14% themselves.
        assert m["line_14_tax_other_rate"] == "700"
        assert m["line_14_tax_30"] == ""
        assert m["line_15_tax_total"] == "700"
        # Column (d)'s rate blank must carry the 14% figure the dollar
        # amount in that column is actually taxed at.
        assert m["line_hdr_other_rate_pct"] == "14"
        assert "Scholarship" in m["line_12_other_specify"]

    def test_non_fjmq_visa_routes_to_30_percent_column(self):
        """A non-F/J/M/Q visa holder (e.g. H-1B) gets no §1441(b) scholarship
        rate reduction — FDAP must land in the 30% column (c), not the
        "Other rate" column, and line 13/14 must both be populated for that
        column (regression guard: an earlier version of this module never
        wired up line 13's 30% box at all, so it silently stayed blank even
        though line 12's 30% box had a real dollar amount in it)."""
        state = _build_china_art20c_state()
        state.residency.exempt_visa_type = None
        state.income.fdap_taxable_total = 1500.0
        state.tax.fdap_tax_liability = 450.0  # 1500 * 30%
        m = compute("Schedule-NEC", state)
        assert m["line_12_scholarship_30"] == "1500"
        assert m["line_13_subtotal_30"] == "1500"
        assert m["line_14_tax_30"] == "450"
        assert m["line_14_tax_other_rate"] == ""
        assert m["line_15_tax_total"] == "450"
        # No custom rate needed — 30% is the form's own printed column header.
        assert m["line_hdr_other_rate_pct"] == ""
        assert m["line_12_other_specify"] == "Other FDAP income"

    def test_partial_treaty_exemption_uses_net_not_gross_fdap(self):
        """When a treaty exempts only PART of the FDAP total, the dollar
        figure entered on lines 12/13 must be the NET (post-treaty) taxable
        amount consistent with the actual computed tax — not the gross
        pre-treaty IncomeState.fdap_taxable_total. Regression guard: an
        earlier version of this module used the gross figure directly,
        which would overstate the reported income relative to the tax
        actually assessed whenever a treaty partially offset FDAP."""
        state = _build_china_art20c_state()
        # Gross 1042-S FDAP is $8,000; a $5,000 treaty exemption on the
        # scholarship_fellowship category leaves $3,000 net, taxed at 14%.
        state.income.fdap_taxable_total = 8000.0
        state.tax.fdap_tax_liability = 420.0  # 3000 * 14%, per l6_tax_calc.py
        m = compute("Schedule-NEC", state)
        assert m["line_12_scholarship_other_rate"] == "3000"
        assert m["line_13_subtotal_other_rate"] == "3000"
        assert m["line_14_tax_other_rate"] == "420"
        assert m["line_15_tax_total"] == "420"


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
        # No SALT cap bite in this fixture, so raw (1a) == capped (1b) == 1800.
        assert m["line_1a_state_local_income_tax"] == "1800"
        assert m["line_1b_salt_cap_amount"] == "1800"
        assert m["line_8_total_itemized"] == "2000"
        assert m["_disallowed_items_warnings"][0].startswith("Mortgage")

    def test_header_name_and_tin_filled(self):
        """Regression guard: f1_1[0]/f1_2[0] (name + identifying number,
        repeated at the top of every attached schedule) were completely
        unmapped in an earlier version of this module."""
        state = _build_china_art20c_state()
        state.sch_a = {"state_local_income_tax": 500.0, "total": 500.0}
        m = compute("Schedule-A", state)
        assert m["header_name"] == "Ming Chen"
        assert m["header_identifying_number"] == "912345678"

    def test_line_1a_reports_raw_pretax_amount_not_capped_amount(self):
        """Regression guard: line 1a must show the RAW pre-SALT-cap
        state+local income tax paid; line 1b shows the capped amount that
        actually flows into the line 8 total. An earlier version of this
        module wrote the already-capped figure onto line 1a (understating
        it whenever the cap bit) and wrote a free-text warning sentence
        onto line 1b instead of the numeric capped amount."""
        state = _build_china_art20c_state()
        state.sch_a = {
            "state_local_income_tax": 40000.0,  # capped (line 1b)
            "salt_cap_bite": 5000.0,            # amount disallowed by the cap
            "charitable_cash": 0.0,
            "charitable_noncash": 0.0,
            "casualty_disaster_loss": 0.0,
            "other_itemized": 0.0,
            "total": 40000.0,
            "disallowed_items": [],
        }
        m = compute("Schedule-A", state)
        assert m["line_1a_state_local_income_tax"] == "45000"  # 40000 + 5000 raw
        assert m["line_1b_salt_cap_amount"] == "40000"
        assert m["line_8_total_itemized"] == "40000"
        assert m["_salt_cap_bite_note"] == "SALT cap reduced the deductible amount by $5,000"

    def test_no_salt_cap_bite_leaves_note_blank(self):
        state = _build_china_art20c_state()
        state.sch_a = {
            "state_local_income_tax": 3000.0,
            "salt_cap_bite": 0.0,
            "total": 3000.0,
        }
        m = compute("Schedule-A", state)
        assert m["line_1a_state_local_income_tax"] == "3000"
        assert m["line_1b_salt_cap_amount"] == "3000"
        assert m["_salt_cap_bite_note"] == ""


class TestForm8843:
    def test_part_iii_populated_for_f1(self):
        state = _build_china_art20c_state()
        m = compute("8843", state)
        assert m["part_I_first_name"] == "Ming"
        assert m["part_I_last_name"] == "Chen"
        assert m["part_I_line_1b_current_status"] == "F-1"
        assert m["_part_III_relevant"] is True
        assert m["_part_II_relevant"] is False
        assert m["_part_IV_relevant"] is False
        assert m["_part_V_relevant"] is False

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
        # Part II's parallel grid must stay blank -- this filer is Part III.
        assert m["part_II_line_7_visa_yr_minus_1"] == ""

    def test_line_12_exempt_more_than_5_years(self):
        state = _build_china_art20c_state()
        state.residency.years_in_exempt_status = 2
        m = compute("8843", state)
        assert m["part_III_line_12_exempt_more_than_5_years_yes"] is False
        assert m["part_III_line_12_exempt_more_than_5_years_no"] is True

        state.residency.years_in_exempt_status = 6
        m = compute("8843", state)
        assert m["part_III_line_12_exempt_more_than_5_years_yes"] is True
        assert m["part_III_line_12_exempt_more_than_5_years_no"] is False

    def test_line_13_lpr_status_defaults_no_when_part_iii_relevant(self):
        """No intake field collects LPR steps; Part III students should
        still get an explicit 'No' box checked, not a blank/unanswered line."""
        state = _build_china_art20c_state()
        m = compute("8843", state)
        assert m["part_III_line_13_applied_for_lpr_status_yes"] is False
        assert m["part_III_line_13_applied_for_lpr_status_no"] is True

    def test_part_ii_routes_j1_teacher_researcher(self):
        """A J-1 teacher/researcher must populate Part II (lines 5-8), not
        Part III -- routing is driven by visa_subtype, not visa_type alone."""
        state = _build_china_art20c_state()
        state.residency.exempt_visa_type = "J-1"
        state.residency.visa_subtype = "teacher_researcher"
        # years_in_exempt_status stays 2 (fixture default) -> first exempt
        # year 2024, which is the yr_minus_1 slot in the 2019-2024 window.
        m = compute("8843", state)
        assert m["_part_II_relevant"] is True
        assert m["_part_II_role"] == "teacher"
        assert m["_part_III_relevant"] is False
        assert m["part_I_line_1b_current_status"] == "J-1"
        assert m["part_II_line_7_visa_yr_minus_1"] == "J-1"  # tax_year - 1
        assert m["part_II_line_7_visa_yr_minus_6"] == ""  # pre-arrival
        # Part III's parallel grid/lines must stay blank for a Part II filer.
        assert m["part_III_line_11_visa_yr_minus_1"] == ""
        assert m["part_III_line_12_exempt_more_than_5_years_yes"] is False
        assert m["part_III_line_12_exempt_more_than_5_years_no"] is False
        assert m["part_III_line_13_applied_for_lpr_status_yes"] is False
        assert m["part_III_line_13_applied_for_lpr_status_no"] is False

    def test_part_ii_routes_j1_trainee(self):
        state = _build_china_art20c_state()
        state.residency.exempt_visa_type = "J-1"
        state.residency.visa_subtype = "trainee"
        m = compute("8843", state)
        assert m["_part_II_relevant"] is True
        assert m["_part_II_role"] == "trainee"

    def test_j1_student_subtype_routes_part_iii(self):
        """A plain J-1 student (visa_subtype='student', the model default)
        still routes to Part III, matching F-1/M-1/Q-1 students."""
        state = _build_china_art20c_state()
        state.residency.exempt_visa_type = "J-1"
        state.residency.visa_subtype = "student"
        m = compute("8843", state)
        assert m["_part_II_relevant"] is False
        assert m["_part_III_relevant"] is True

    def test_line_8_exempt_2_of_preceding_6_years(self):
        state = _build_china_art20c_state()
        state.residency.exempt_visa_type = "J-1"
        state.residency.visa_subtype = "teacher_researcher"
        state.residency.years_in_exempt_status = 2
        m = compute("8843", state)
        assert m["part_II_line_8_exempt_2_of_6_yes"] is False
        assert m["part_II_line_8_exempt_2_of_6_no"] is True

        state.residency.years_in_exempt_status = 3
        m = compute("8843", state)
        assert m["part_II_line_8_exempt_2_of_6_yes"] is True
        assert m["part_II_line_8_exempt_2_of_6_no"] is False

    def test_line_1a_includes_entry_date_when_available(self):
        state = _build_china_art20c_state()
        state.residency.first_us_entry_date = "2023-08-15"
        m = compute("8843", state)
        assert m["part_I_line_1a_visa_and_entry_date"] == "F-1, entered 08/15/2023"

    def test_line_1a_blank_entry_date_falls_back_to_visa_only(self):
        state = _build_china_art20c_state()
        state.residency.first_us_entry_date = None
        m = compute("8843", state)
        assert m["part_I_line_1a_visa_and_entry_date"] == "F-1"

    def test_us_and_foreign_address_include_line2(self):
        state = _build_china_art20c_state()
        state.identity.us_address_line2 = "Apt 4B"
        state.identity.foreign_address_line1 = "88 Nanjing Rd"
        state.identity.foreign_address_line2 = "Unit 12"
        state.identity.foreign_city = "Shanghai"
        state.identity.foreign_country = "CN"
        m = compute("8843", state)
        assert "Apt 4B" in m["part_I_address_us_line1"]
        assert "Unit 12" in m["part_I_address_foreign_line1"]


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

    def test_addresses_populated_from_identity(self):
        """Regression: box_1d/box_1e were previously left off the field map
        entirely, so the real PDF's 'Address in country of residence' /
        'Address in the United States' lines rendered blank."""
        state = _build_china_art20c_state()
        state.identity.foreign_address_line1 = "88 Nanjing Rd"
        state.identity.foreign_city = "Shanghai"
        state.identity.foreign_country = "CN"
        m = compute("8833", state)
        row = m["rows"][0]
        assert "88 Nanjing Rd" in row["box_1d_address_foreign"]
        assert "Shanghai" in row["box_1d_address_foreign"]
        assert "123 Beacon St Apt 4" in row["box_1e_address_us"]
        assert "Boston" in row["box_1e_address_us"]
        assert "MA" in row["box_1e_address_us"]

    def test_section_6114_box_checked_dual_resident_box_never_checked(self):
        """This engine only ever discloses ordinary §6114 treaty positions,
        never a §7701(b) dual-resident election, so the top checkbox pair
        must be checked/unchecked accordingly on every row."""
        state = _build_china_art20c_state()
        m = compute("8833", state)
        row = m["rows"][0]
        assert row["box_check_6114"] == "/1"
        assert row["box_check_dual_resident"] == "/Off"

    def test_us_citizen_or_resident_box_reflects_residency_status(self):
        """Regression: this checkbox was previously left unmapped. It must
        track the actual residency determination, not a hardcoded value."""
        state = _build_china_art20c_state()
        state.residency.status = "nonresident_alien"
        m = compute("8833", state)
        assert m["rows"][0]["box_check_us_citizen_or_resident"] == "/Off"

        state.residency.status = "resident_alien"
        m = compute("8833", state)
        assert m["rows"][0]["box_check_us_citizen_or_resident"] == "/1"

    def test_line_5_reg_6114_1b_yes_checked_for_every_generated_row(self):
        """A row only exists here because treaty_evaluator already
        determined IRC §6114/Reg 301.6114-1(b) reporting is required (net of
        the Notice 2010-21 routine-position exception) -- so Line 5 must
        always read 'Yes', never blank/'No'."""
        state = _build_china_art20c_state()
        m = compute("8833", state)
        row = m["rows"][0]
        assert row["box_5_reg_6114_1b_yes"] == "/1"
        assert row["box_5_reg_6114_1b_no"] == "/Off"

    def test_line_6_explanation_includes_dollar_amount(self):
        """Form 8833 has no standalone 'amount exempted' field -- the real
        Line 6 instructions require the dollar amount to be part of the
        written explanation. Regression: the amount used to be written to
        its own isolated field (f1_13) instead."""
        state = _build_china_art20c_state()
        state.treaty.applied_benefits[0]["explanation"] = "Bare-bones explanation with no dollar figure."
        state.treaty.applied_benefits[0]["exempt_amount"] = 5000.0
        m = compute("8833", state)
        row = m["rows"][0]
        assert "$5,000" in row["box_5_explanation"]
        assert row["box_5_explanation_rows"], "explanation must be split into line rows for the PDF"
        joined = " ".join(r["text"] for r in row["box_5_explanation_rows"])
        assert "$5,000" in joined

    def test_line_6_explanation_wraps_across_at_most_25_single_line_fields(self):
        """f1_12..f1_36 are 25 genuinely single-line (non-multiline) text
        fields on the real PDF -- a long explanation must be word-wrapped
        across them, not silently dumped unwrapped into one field."""
        state = _build_china_art20c_state()
        state.treaty.applied_benefits[0]["explanation"] = "word " * 400
        m = compute("8833", state)
        rows = m["rows"][0]["box_5_explanation_rows"]
        assert 1 < len(rows) <= 25
        for r in rows:
            assert len(r["text"]) <= 95  # generous bound over the widest (f1_13..f1_36) slot

    def test_line_6_saving_clause_note_appended_when_applicable_but_not_duplicated(self):
        state = _build_china_art20c_state()
        state.treaty.applied_benefits[0]["applies_after_saving_clause"] = True
        state.treaty.applied_benefits[0]["explanation"] = "No mention of the S-word here."
        m = compute("8833", state)
        text = m["rows"][0]["box_5_explanation"]
        assert "saving clause" in text.lower()

        # When the source explanation already mentions the saving clause
        # (as treaty_evaluator._build_explanation does), no addendum is
        # appended on top of it.
        state.treaty.applied_benefits[0]["explanation"] = (
            "Article 20(c): exempts $5,000; saving-clause exception applies."
        )
        m = compute("8833", state)
        text2 = m["rows"][0]["box_5_explanation"]
        assert text2.count("saving-clause exception applies") == 1
        assert "notwithstanding the treaty's saving clause" not in text2

    def test_multiple_benefits_produce_independent_non_cross_contaminated_rows(self):
        state = _build_china_art20c_state()
        state.treaty.applied_benefits = [
            {
                "country_name": "China (People's Republic of)",
                "article_id": "20(c)",
                "category": "student_personal_services",
                "explanation": "Wage exemption row.",
                "exempt_amount": 5000.0,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
            },
            {
                "country_name": "China (People's Republic of)",
                "article_id": "20(b)",
                "category": "scholarship_fellowship",
                "explanation": "Scholarship exemption row.",
                "exempt_amount": 3000.0,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
            },
        ]
        m = compute("8833", state)
        assert m["count"] == 2
        row1, row2 = m["rows"]
        assert row1["box_3_treaty_article"] == "20(c)"
        assert row2["box_3_treaty_article"] == "20(b)"
        assert "$5,000" in row1["box_5_explanation"] and "$3,000" not in row1["box_5_explanation"]
        assert "$3,000" in row2["box_5_explanation"] and "$5,000" not in row2["box_5_explanation"]


class TestForm843:
    def test_explanation_and_amounts(self):
        state = _build_china_art20c_state()
        m = compute("843", state)
        assert m["line_1_amount_to_refund"] == "2295"  # 1860 + 435, whole-dollar formatted
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


class TestForm8316:
    """Form 8316's yes/no/do-not-know answers are fixed given QuadTax's
    FICA-refund path (filing 843 at all presupposes the underlying facts —
    see the module docstring), but they must be the *real* multi-state
    radio-group export strings ('/1'/'/2'/'/3'), not bare Python bools —
    field '5' in particular has a real third state ('/3' = Do not Know)
    that a bool-plus-/_States_-fallback would never reach."""

    def test_fixed_yes_no_dnk_answers_use_real_export_states(self):
        state = _build_china_art20c_state()
        m = compute("8316", state)
        assert m["q_a_income_per_visa"] == "/1"  # Yes
        assert m["q1_employer_repaid"] == "/2"  # No
        assert m["q3_authorized_employer_claim"] == "/2"  # No
        assert m["q5_employer_claimed"] == "/3"  # Do Not Know
        assert m["q7_claimed_against_federal_tax"] == "/2"  # No
        # None of the "if yes, show amount" lines apply since every
        # underlying question is answered No/Do Not Know, not Yes.
        assert m["q1_employer_repaid_amount"] == ""
        assert m["q3_authorized_employer_claim_amount"] == ""
        assert m["q5_employer_claimed_amount"] == ""
        assert m["q7_claimed_against_federal_tax_amount"] == ""

    def test_employer_name_and_phone_flow_through(self):
        state = _build_china_art20c_state()
        state.income.employer_name = "Boston University"
        state.identity.daytime_phone = "617-555-0199"
        m = compute("8316", state)
        assert m["employer_name"] == "Boston University"
        assert m["signature_phone"] == "617-555-0199"


class TestFormW7:
    def test_reason_code_a_when_treaty_claim(self):
        state = _build_china_art20c_state()
        m = compute("W-7", state)
        assert m["reason_code"] == "a"
        assert m["passport_number"] == "E12345678"
        assert m["treaty_country_when_reason_a"] == "CN"
        assert m["treaty_article_when_reason_a"] == "20(c)"
        # Reason a and reason h are BOTH true: the real W-7's printed
        # instructions for box a are unconditional ("you must also check
        # and complete box h"), verified against the vendored PDF's text.
        assert m["reason_a"] is True
        assert m["reason_h"] is True
        for letter in "bcdefg":
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
        # Reason f doesn't trigger box h (this engine always attaches W-7
        # to a real 1040-NR, so the "claiming an exception" branch of box
        # f's instructions — the only sub-case requiring box h — never
        # applies).
        assert m["treaty_country_when_reason_a"] == ""
        assert m["treaty_article_when_reason_a"] == ""

    def test_treaty_country_uses_the_specific_8833_benefit_not_scalar_primary(self):
        """Regression test: a multi-article-treaty filer whose *primary*
        (largest-exemption) TreatyState fields point at a different article
        than the one actually requiring Form 8833 must still get the 8833
        benefit's own country/article on the W-7, not the scalar fields."""
        state = _build_china_art20c_state()
        state.treaty.country = "IN"  # scalar "primary" fields deliberately mismatched
        state.treaty.article_number = "21(2)"
        state.treaty.applied_benefits = [
            {
                "country_iso2": "CN",
                "article_id": "20(b)",
                "requires_form_8833": False,  # larger exemption, but no 8833 needed
            },
            {
                "country_iso2": "CN",
                "article_id": "20(c)",
                "requires_form_8833": True,  # smaller exemption, but THIS one needs 8833
            },
        ]
        m = compute("W-7", state)
        assert m["reason_code"] == "a"
        assert m["treaty_country_when_reason_a"] == "CN"
        assert m["treaty_article_when_reason_a"] == "20(c)"

    def test_renewal_flag_reflects_itin_eligibility(self):
        state = _build_china_art20c_state()
        state.itin_eligibility = {"is_renewal": True}
        m = compute("W-7", state)
        assert m["application_type_new"] is False
        assert m["application_type_renewal"] is True
        # Line 6e/6f: previously-received-ITIN flips to Yes and the prior
        # ITIN (from identity.itin, "912345678" in the base fixture) is
        # split into the real PDF's XXX-XX-XXXX comb groups.
        assert m["previously_received_itin_no"] is False
        assert m["previously_received_itin_yes"] is True
        assert m["prior_itin_group1"] == "912"
        assert m["prior_itin_group2"] == "34"
        assert m["prior_itin_group3"] == "5678"
        assert m["prior_itin_name_first"] == "Ming"
        assert m["prior_itin_name_last"] == "Chen"

    def test_first_application_leaves_prior_itin_fields_blank(self):
        state = _build_china_art20c_state()
        state.itin_eligibility = {"is_renewal": False}
        m = compute("W-7", state)
        assert m["previously_received_itin_no"] is True
        assert m["previously_received_itin_yes"] is False
        assert m["prior_itin_group1"] == ""
        assert m["prior_itin_group2"] == ""
        assert m["prior_itin_group3"] == ""
        assert m["prior_itin_name_first"] == ""

    def test_name_split_across_the_three_real_pdf_boxes(self):
        """Regression test: line 1a is three separate boxes (First/Middle/
        Last name) on the real PDF; the name must not be crammed into a
        single field, which would leave the actual last-name box blank."""
        state = _build_china_art20c_state()
        state.identity.middle_initial = "Q"
        m = compute("W-7", state)
        assert m["first_name"] == "Ming"
        assert m["middle_initial"] == "Q"
        assert m["last_name"] == "Chen"
        # Line 1b ("name at birth if different") has no backing data and
        # must not be silently filled in with the current name.
        assert "name_at_birth" not in m
        assert "name_line1" not in m

    def test_passport_id_document_checkbox_and_entry_date(self):
        state = _build_china_art20c_state()
        state.residency.first_us_entry_date = "2023-08-15"
        m = compute("W-7", state)
        assert m["id_doc_passport"] is True
        assert m["us_entry_date"] == "08152023"
        assert m["visa_type"] == "F-1"

    def test_no_passport_number_leaves_id_document_checkbox_unset(self):
        state = _build_china_art20c_state()
        state.identity.passport_number = ""
        m = compute("W-7", state)
        assert m["id_doc_passport"] is False


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

    def test_line_9_and_10_not_swapped(self):
        """Regression test: line 9 (Tentative minimum tax, after AMT FTC)
        was being overwritten with regular_tax_for_amt, and line 10
        (regular tax) was left entirely blank — a genuine line-swap bug
        that also broke the printed line 11 = line 9 - line 10 math.

        Since this engine has no AMT foreign tax credit computation, line 8
        is blank/zero, so line 9 must equal line 7 (tentative_minimum_tax)
        exactly; line 10 must carry the regular tax figure instead.
        """
        state = _build_china_art20c_state()
        state.amt = {
            "amti": 100000.0,
            "exemption": 88100.0,
            "tentative_minimum_tax": 3100.0,
            "regular_tax_for_amt": 2762.0,
            "amt_owed": 338.0,
            "binds": True,
        }
        m = compute("6251", state)
        assert m["line_7_tmt_before_credits"] == "3100"
        assert m["line_9_tmt_after_ftc"] == "3100"
        assert m["line_10_regular_tax"] == "2762"
        assert m["line_11_amt_owed"] == "338"

    def test_line_6_derived_from_amti_minus_exemption(self):
        """Line 6 ('Subtract line 5 from line 4') isn't stored on AMTResult
        directly but must be derived from amti/exemption, not left blank."""
        state = _build_china_art20c_state()
        state.amt = {
            "amti": 100000.0,
            "exemption": 88100.0,
            "tentative_minimum_tax": 3094.0,
            "regular_tax_for_amt": 2762.0,
            "amt_owed": 332.0,
            "binds": True,
        }
        m = compute("6251", state)
        assert m["line_6_less_exemption"] == "11900"

    def test_line_6_floors_at_zero_when_exemption_exceeds_amti(self):
        state = _build_china_art20c_state()
        state.amt = {
            "amti": 50000.0,
            "exemption": 88100.0,
            "tentative_minimum_tax": 0.0,
            "regular_tax_for_amt": 500.0,
            "amt_owed": 0.0,
            "binds": False,
        }
        m = compute("6251", state)
        assert m["line_6_less_exemption"] == ""


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
        assert m["line_34_overpaid"] == "2878"

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
        NYTaxState, so the form that displays them had nothing to read.

        Field-map keys match the real vendored IT-203-B's line numbering
        (1a-1p), verified against the actual PDF's AcroForm structure —
        not the placeholder keys used before real templates existed."""
        state = _build_china_art20c_state()
        state.ny.ny_work_days = 180
        state.ny.total_work_days = 200
        state.ny.abode_months_in_year = 9
        m = compute("IT-203-B", state)
        assert m["1l"] == "180"  # days worked in NY
        assert m["1h"] == "200"  # total days worked at this job
        assert m["1i"] == "20"  # days (of 1h) worked outside NY
        assert m["1n"] == "0.9000"  # 1l / 1m = 180/200
        # Real form only has a binary "maintained for the entire tax
        # year" checkbox for Schedule B — no free-text month count.
        assert "quarters_maintained_all_year" not in m

    def test_quarters_maintained_checkbox_only_when_full_year(self):
        state = _build_china_art20c_state()
        state.ny.abode_months_in_year = 12
        m = compute("IT-203-B", state)
        assert m["quarters_maintained_all_year"] == "/Yes"

    def test_workday_outside_ny_never_negative(self):
        state = _build_china_art20c_state()
        state.ny.ny_work_days = 50
        state.ny.total_work_days = 0  # not yet populated
        m = compute("IT-203-B", state)
        assert m["1i"] == "0"

    def test_1n_uses_wage_day_ratio_not_blended_income_percentage(self):
        """1n must match the exact ratio ny_source_allocator used to
        compute ny_source_wages (line 1p) — NOT ny.ny_income_percentage,
        which also folds in 1042-S/FDAP allocation and can diverge from
        the pure wage-day ratio."""
        state = _build_china_art20c_state()
        state.ny.ny_work_days = 100
        state.ny.total_work_days = 200
        state.ny.ny_income_percentage = 0.75  # deliberately different
        m = compute("IT-203-B", state)
        assert m["1n"] == "0.5000"


class TestFormIT203:
    def test_identity_filing_status_and_wage_lines(self):
        state = _build_china_art20c_state()
        state.ny.ny_source_wages = 25000.0
        state.ny.ny_agi = 30000.0
        state.ny.ny_source_income = 25000.0
        m = compute("IT-203", state)
        assert m["your_first_name"] == "Ming"
        assert m["your_last_name"] == "Chen"
        assert m["filing_status"] == "/1 Single"
        assert m["line_1_federal"] == "30000"
        assert m["line_1_ny"] == "25000"
        assert m["line_31_federal"] == "30000"
        assert m["line_31_ny"] == "25000"

    def test_mfs_spouse_fields_populated(self):
        """IT-203, unlike the federal 1040-NR, has real spouse ID lines."""
        state = _build_china_art20c_state()
        state.identity.filing_status = "mfs"
        state.identity.spouse_first_name = "Wei"
        state.identity.spouse_last_name = "Chen"
        state.identity.spouse_ssn_or_itin = "912345670"
        m = compute("IT-203", state)
        assert "Married Filing Seperate" in m["filing_status"]
        assert m["spouse_first_name"] == "Wei"
        assert m["spouse_last_name"] == "Chen"
        assert m["spouse_ssn"] == "912345670"

    def test_no_spouse_fields_when_ssn_not_provided(self):
        state = _build_china_art20c_state()
        state.identity.filing_status = "mfs"
        m = compute("IT-203", state)
        assert "spouse_first_name" not in m

    def test_dependent_checkbox_reflects_extras(self):
        state = _build_china_art20c_state()
        state.extras.can_be_claimed_as_dependent = True
        m = compute("IT-203", state)
        assert m["item_c_dependent"] == "/yes"

    def test_treaty_addback_lands_on_lines_18_and_22(self):
        state = _build_china_art20c_state()
        state.ny.ny_treaty_addback = 5000.0
        state.ny.ny_agi = 35000.0
        m = compute("IT-203", state)
        assert m["line_18_federal"] == "5000"
        assert m["line_22_federal"] == "5000"

    def test_no_treaty_addback_omits_line_18_and_blanks_line_22(self):
        state = _build_china_art20c_state()
        state.ny.ny_treaty_addback = 0.0
        m = compute("IT-203", state)
        # Line 18 ("Total federal adjustments, Identify") is a conditional
        # text+amount pair only meaningful with a treaty exemption to name.
        assert "line_18_federal" not in m
        # Line 22 is an ordinary money line (like every other numbered
        # line on this form) — always present, blank when $0, matching
        # the _fmt_money convention used throughout this codebase.
        assert m["line_22_federal"] == ""

    def test_itemized_vs_standard_deduction_checkbox(self):
        state = _build_china_art20c_state()
        state.ny.ny_standard_deduction = 8000.0
        m = compute("IT-203", state)
        assert m["deduction_type"] == "/Standard"

        state.sch_a = {"total": 3000.0}
        m = compute("IT-203", state)
        assert m["deduction_type"] == "/Itemized"

    def test_direct_deposit_only_marked_when_refund_owed(self):
        state = _build_china_art20c_state()
        state.tax.direct_deposit = True
        state.tax.routing_number = "021000021"
        state.tax.account_number = "12345"
        state.ny.ny_refund_or_owed = 100.0  # amount owed, no refund
        m = compute("IT-203", state)
        assert "refund_method" not in m

        state.ny.ny_refund_or_owed = -100.0  # refund due
        m = compute("IT-203", state)
        assert m["refund_method"] == "/direct deposit"
        assert m["routing_number"] == "021000021"


class TestFormIT203D:
    def test_salt_addback_and_final_deduction(self):
        state = _build_china_art20c_state()
        state.sch_a = {
            "total": 3200.0,
            "state_local_income_tax": 1200.0,
            "charitable_cash": 2000.0,
        }
        m = compute("IT-203-D", state)
        assert m["line_2_taxes_paid"] == "1200"
        assert m["line_4_charity"] == "2000"
        assert m["line_8_total"] == "3200"
        assert m["line_9_salt_addback"] == "1200"
        # NY disallows SALT: final NY itemized = federal total - SALT.
        assert m["line_10"] == "2000"
        assert m["line_15_ny_itemized"] == "2000"

    def test_no_state_local_tax_no_addback(self):
        state = _build_china_art20c_state()
        state.sch_a = {"total": 500.0, "charitable_cash": 500.0}
        m = compute("IT-203-D", state)
        assert m["line_9_salt_addback"] == ""
        assert m["line_10"] == "500"
