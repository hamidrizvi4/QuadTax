"""Tests for the post-layer reasonability validators."""

from src.orchestrator.state import ReturnStateObject
from src.orchestrator.validators import (
    MAX_REASONABLE_FICA_REFUND,
    MAX_REASONABLE_WAGES,
    run_validator,
    validate_post_l1,
    validate_post_l3,
    validate_post_l4,
    validate_post_l6,
    validate_post_l8,
)


class TestPostL1:
    def test_negative_spt_days_flagged(self):
        state = ReturnStateObject()
        state.residency.spt_days_current_year = -5  # type: ignore[assignment]
        validate_post_l1(state)
        assert any("SPT day count" in r for r in state.requires_human_review)

    def test_implausible_years_flagged(self):
        state = ReturnStateObject()
        state.residency.years_in_exempt_status = 50
        validate_post_l1(state)
        assert any("years_in_exempt_status" in r for r in state.requires_human_review)

    def test_normal_case_no_flag(self):
        state = ReturnStateObject()
        state.residency.spt_days_current_year = 300
        state.residency.years_in_exempt_status = 2
        validate_post_l1(state)
        assert state.requires_human_review == []

    def test_negative_days_present_year_minus_1_flagged(self):
        """Raw I-94 day counts for prior years are assigned onto state
        straight from LLM extraction (see l1_residency.py) with no
        Pydantic re-validation on assignment — a garbled OCR scan can
        leave a negative value here that also feeds the SPT weighted
        formula and gets printed on Form 8843 / Schedule OI verbatim."""
        state = ReturnStateObject()
        state.residency.days_present_year_minus_1 = -50  # type: ignore[assignment]
        validate_post_l1(state)
        assert any(
            "tax_year - 1" in r and "outside 0-366" in r
            for r in state.requires_human_review
        )

    def test_excessive_days_present_year_minus_2_flagged(self):
        state = ReturnStateObject()
        state.residency.days_present_year_minus_2 = 999  # type: ignore[assignment]
        validate_post_l1(state)
        assert any(
            "tax_year - 2" in r and "outside 0-366" in r
            for r in state.requires_human_review
        )

    def test_negative_days_present_current_year_flagged(self):
        state = ReturnStateObject()
        state.residency.days_present_current_year = -1  # type: ignore[assignment]
        validate_post_l1(state)
        assert any(
            "current year" in r and "outside 0-366" in r
            for r in state.requires_human_review
        )

    def test_in_range_raw_day_counts_not_flagged(self):
        state = ReturnStateObject()
        state.residency.days_present_current_year = 300
        state.residency.days_present_year_minus_1 = 365
        state.residency.days_present_year_minus_2 = 0
        validate_post_l1(state)
        assert state.requires_human_review == []

    def test_resident_alien_status_flagged(self):
        """A resident-alien classification (exempt window expired, or SPT
        independently met) needs Form 1040, not the 1040-NR this engine
        generates — must route to human review, not silently assemble the
        wrong form."""
        state = ReturnStateObject()
        state.residency.status = "resident_alien"
        validate_post_l1(state)
        assert any("resident alien" in r for r in state.requires_human_review)

    def test_married_but_filing_single_flagged(self):
        state = ReturnStateObject()
        state.extras.was_married_on_last_day = True
        state.identity.filing_status = "single"
        validate_post_l1(state)
        assert any("married" in r.lower() for r in state.requires_human_review)

    def test_married_filing_mfs_not_flagged(self):
        state = ReturnStateObject()
        state.extras.was_married_on_last_day = True
        state.identity.filing_status = "mfs"
        validate_post_l1(state)
        assert state.requires_human_review == []

    def test_not_married_filing_single_not_flagged(self):
        state = ReturnStateObject()
        state.extras.was_married_on_last_day = False
        state.identity.filing_status = "single"
        validate_post_l1(state)
        assert state.requires_human_review == []

    def test_6013g_election_flagged(self):
        state = ReturnStateObject()
        state.elections.section_6013g_election = True
        validate_post_l1(state)
        assert any("6013" in r for r in state.requires_human_review)

    def test_6013h_election_flagged(self):
        state = ReturnStateObject()
        state.elections.section_6013h_election = True
        validate_post_l1(state)
        assert any("6013" in r for r in state.requires_human_review)

    def test_871d_election_flagged(self):
        state = ReturnStateObject()
        state.elections.section_871d_election = True
        validate_post_l1(state)
        assert any("871(d)" in r for r in state.requires_human_review)

    def test_large_foreign_gifts_flagged(self):
        state = ReturnStateObject()
        state.elections.large_foreign_gifts_over_100k = True
        validate_post_l1(state)
        assert any("3520" in r for r in state.requires_human_review)

    def test_closer_connection_flagged(self):
        state = ReturnStateObject()
        state.elections.closer_connection_exception_claimed = True
        validate_post_l1(state)
        assert any("8840" in r for r in state.requires_human_review)

    def test_no_elections_no_flag(self):
        state = ReturnStateObject()
        state.residency.spt_days_current_year = 300
        state.residency.years_in_exempt_status = 2
        validate_post_l1(state)
        assert state.requires_human_review == []


class TestPostL3:
    def test_negative_wages_flagged(self):
        state = ReturnStateObject()
        # Bypass Pydantic validation for the unit test.
        state.income.total_w2_wages = -1.0  # type: ignore[assignment]
        validate_post_l3(state)
        assert any("negative W-2 wages" in r for r in state.requires_human_review)

    def test_extreme_wages_flagged(self):
        state = ReturnStateObject()
        state.income.total_w2_wages = MAX_REASONABLE_WAGES + 1.0
        validate_post_l3(state)
        assert any("reasonability ceiling" in r for r in state.requires_human_review)

    def test_excessive_withholding_flagged(self):
        state = ReturnStateObject()
        state.income.total_w2_wages = 30000.0
        state.income.total_w2_withholding = 25000.0  # > 60% of wages
        validate_post_l3(state)
        assert any("60%" in r for r in state.requires_human_review)

    def test_normal_case_no_flag(self):
        state = ReturnStateObject()
        state.income.total_w2_wages = 30000.0
        state.income.total_w2_withholding = 4500.0
        validate_post_l3(state)
        assert state.requires_human_review == []

    def test_negative_w2_withholding_flagged(self):
        """A garbled OCR sign error (e.g. a misread parenthesis) can leave
        a negative federal-withholding figure on state with no exception
        raised anywhere upstream — this silently understates tax already
        paid. Must be flagged for human review."""
        state = ReturnStateObject()
        state.income.total_w2_withholding = -4500.0  # type: ignore[assignment]
        validate_post_l3(state)
        assert any(
            "negative W-2 federal withholding" in r
            for r in state.requires_human_review
        )

    def test_negative_1042s_withholding_flagged(self):
        state = ReturnStateObject()
        state.income.total_1042s_withholding = -700.0  # type: ignore[assignment]
        validate_post_l3(state)
        assert any(
            "negative 1042-S federal withholding" in r
            for r in state.requires_human_review
        )


class TestPostL4:
    def test_treaty_eligible_without_country_flagged(self):
        state = ReturnStateObject()
        state.treaty.is_eligible = True
        state.treaty.country = None
        state.treaty.article_number = "20(c)"
        validate_post_l4(state)
        assert any("no country recorded" in r for r in state.requires_human_review)

    def test_treaty_exempt_exceeds_income_flagged(self):
        state = ReturnStateObject()
        state.treaty.is_eligible = True
        state.treaty.country = "CN"
        state.treaty.article_number = "20(c)"
        state.treaty.exempt_amount_applied = 100000.0
        state.income.total_w2_wages = 30000.0
        validate_post_l4(state)
        assert any("exceeds" in r for r in state.requires_human_review)


class TestPostL6:
    def test_negative_tax_flagged(self):
        state = ReturnStateObject()
        state.tax.total_tax_liability = -10.0
        validate_post_l6(state)
        assert any("negative tax" in r for r in state.requires_human_review)

    def test_tax_exceeds_income_flagged(self):
        state = ReturnStateObject()
        state.income.total_w2_wages = 30000.0
        state.tax.total_tax_liability = 50000.0
        validate_post_l6(state)
        assert any("exceeds total" in r for r in state.requires_human_review)


class TestPostL8:
    def test_huge_fica_refund_flagged(self):
        state = ReturnStateObject()
        state.fica.incorrect_ss_withheld = MAX_REASONABLE_FICA_REFUND + 100
        validate_post_l8(state)
        assert any("FICA refund claim" in r for r in state.requires_human_review)

    def test_843_requested_without_amount_flagged(self):
        state = ReturnStateObject()
        state.fica.requires_form_843 = True
        validate_post_l8(state)
        assert any("no FICA amount" in r for r in state.requires_human_review)


class TestDispatch:
    def test_run_validator_dispatches_to_l3(self):
        state = ReturnStateObject()
        state.income.total_w2_wages = MAX_REASONABLE_WAGES + 1
        run_validator(state, "L3")
        assert state.requires_human_review

    def test_run_validator_no_op_for_unknown_layer(self):
        state = ReturnStateObject()
        result = run_validator(state, "L99")
        assert result == []
