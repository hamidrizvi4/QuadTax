"""Tests for the multi-article treaty evaluator (Phase 1).

The evaluator loads every per-country JSON under
``database/tax_year/2025/treaties/`` and applies article rules deterministically.
"""

import pytest

from src.functions.treaty_evaluator import TreatyEvaluator


@pytest.fixture(scope="module")
def evaluator():
    return TreatyEvaluator(tax_year=2025)


class TestChinaTreaty:
    """China has three relevant articles for NRA students."""

    def test_china_art_20c_5k_cap(self, evaluator):
        """A Chinese F-1 with $30k US wages claims $5k under Art 20(c)."""
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"student_personal_services": 30000.0},
        )
        assert len(benefits) == 1
        b = benefits[0]
        assert b.article_id == "20(c)"
        assert b.exempt_amount == 5000.0
        assert b.requires_form_8833 is True  # threshold is 0
        assert b.applies_after_saving_clause is False

    def test_china_art_19_3yr_expires(self, evaluator):
        """Chinese J-1 researcher in year 4 — Art 19 (3-year cap) no longer applies."""
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="J-1",
            residency_status="nonresident_alien",
            years_since_arrival=4,
            gross_by_category={"teaching_research": 60000.0},
            is_us_source_by_category={"teaching_research": True},
        )
        assert benefits == []

    def test_china_art_19_within_window(self, evaluator):
        """Chinese J-1 researcher in year 2 — Art 19 fully exempts."""
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="J-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"teaching_research": 60000.0},
            is_us_source_by_category={"teaching_research": True},
        )
        assert any(b.article_id == "19" and b.exempt_amount == 60000.0 for b in benefits)

    def test_china_art_20b_scholarship_unlimited(self, evaluator):
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=3,
            gross_by_category={"scholarship_fellowship": 22000.0},
        )
        assert any(
            b.article_id == "20(b)" and b.exempt_amount == 22000.0 for b in benefits
        )

    def test_china_art_20c_survives_saving_clause(self, evaluator):
        """Chinese student in year 6 (resident alien) keeps Art 20(c) via saving-clause exception."""
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="F-1",
            residency_status="resident_alien",
            years_since_arrival=6,
            gross_by_category={"student_personal_services": 30000.0},
        )
        assert any(b.article_id == "20(c)" for b in benefits)
        assert any(b.applies_after_saving_clause for b in benefits)

    def test_china_art_19_does_not_survive_saving_clause(self, evaluator):
        """Article 19 (teaching) does NOT have a saving-clause exception."""
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="J-1",
            residency_status="resident_alien",
            years_since_arrival=2,
            gross_by_category={"teaching_research": 60000.0},
        )
        # Either no benefits or none for Art 19.
        assert all(b.article_id != "19" for b in benefits)


class TestIndiaTreaty:
    """India has two relevant articles for NRA students."""

    def test_india_art_21_1_foreign_source_only(self, evaluator):
        """India Art 21(1) only exempts foreign-source scholarships."""
        # When marked us-source, the article should NOT apply.
        benefits_us = evaluator.evaluate(
            country="IN",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"scholarship_fellowship": 20000.0},
            is_us_source_by_category={"scholarship_fellowship": True},
        )
        assert all(b.article_id != "21(1)" for b in benefits_us)

        # When foreign-source, it should apply.
        benefits_foreign = evaluator.evaluate(
            country="IN",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"scholarship_fellowship": 20000.0},
            is_us_source_by_category={"scholarship_fellowship": False},
        )
        assert any(b.article_id == "21(1)" for b in benefits_foreign)

    def test_india_art_21_2_standard_deduction_path(self, evaluator):
        """Article 21(2) emits the wage-category benefit used by L6 to apply the standard deduction."""
        benefits = evaluator.evaluate(
            country="IN",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"student_personal_services": 20000.0},
            is_us_source_by_category={"student_personal_services": True},
        )
        assert any(b.article_id == "21(2)" for b in benefits)


class TestKoreaTreaty:
    def test_korea_2k_cap_5yr_window(self, evaluator):
        benefits = evaluator.evaluate(
            country="KR",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=3,
            gross_by_category={"student_personal_services": 10000.0},
            is_us_source_by_category={"student_personal_services": True},
        )
        assert any(b.exempt_amount == 2000.0 for b in benefits)

    def test_korea_after_5_years_window_closes(self, evaluator):
        benefits = evaluator.evaluate(
            country="KR",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=6,
            gross_by_category={"student_personal_services": 10000.0},
            is_us_source_by_category={"student_personal_services": True},
        )
        assert all(b.article_id != "21(1)" or b.category != "student_personal_services" for b in benefits)


class TestGermanyTreaty:
    def test_germany_9k_cap_4yr(self, evaluator):
        benefits = evaluator.evaluate(
            country="DE",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"student_personal_services": 20000.0},
            is_us_source_by_category={"student_personal_services": True},
        )
        assert any(b.exempt_amount == 9000.0 for b in benefits)


class TestUKTreaty:
    def test_uk_foreign_source_only(self, evaluator):
        """UK Article 20A applies only to foreign-source remittances."""
        # US-source wages — no UK exemption.
        benefits_us = evaluator.evaluate(
            country="GB",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=1,
            gross_by_category={"foreign_source_remittance": 40000.0},
            is_us_source_by_category={"foreign_source_remittance": True},
        )
        assert benefits_us == []

        # Foreign-source — full exemption.
        benefits_foreign = evaluator.evaluate(
            country="GB",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=1,
            gross_by_category={"foreign_source_remittance": 40000.0},
            is_us_source_by_category={"foreign_source_remittance": False},
        )
        assert any(b.exempt_amount == 40000.0 for b in benefits_foreign)


class TestNoTreaty:
    def test_brazil_no_treaty(self, evaluator):
        """Brazil has no income tax treaty with the US (verify graceful handling)."""
        benefits = evaluator.evaluate(
            country="BR",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"student_personal_services": 20000.0},
        )
        assert benefits == []

    def test_hungary_treaty_terminated(self, evaluator):
        """Hungary treaty terminated effective 2024 — no benefits."""
        benefits = evaluator.evaluate(
            country="HU",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=1,
            gross_by_category={"student_personal_services": 20000.0},
        )
        assert benefits == []


class TestForm8833Aggregator:
    def test_8833_aggregator_true_when_any_benefit_triggers(self, evaluator):
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={"student_personal_services": 30000.0},
        )
        assert TreatyEvaluator.aggregate_form_8833_required(benefits) is True

    def test_total_exempt_by_category(self, evaluator):
        benefits = evaluator.evaluate(
            country="CN",
            visa_type="F-1",
            residency_status="nonresident_alien",
            years_since_arrival=2,
            gross_by_category={
                "student_personal_services": 30000.0,
                "scholarship_fellowship": 10000.0,
            },
        )
        totals = TreatyEvaluator.total_exempt_by_category(benefits)
        assert totals.get("student_personal_services") == 5000.0
        assert totals.get("scholarship_fellowship") == 10000.0


class TestSeededCoverage:
    """Spot-check that the seeded database has the expected countries."""

    def test_count_is_at_least_60(self, evaluator):
        assert len(evaluator.countries) >= 60

    def test_high_volume_countries_present(self, evaluator):
        for iso in ["CN", "IN", "KR", "DE", "GB", "CA", "PK", "JP", "MX", "ES", "FR"]:
            assert evaluator.country(iso) is not None, f"Missing {iso}"
