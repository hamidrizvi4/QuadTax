"""Audit-state assertions for the top-volume filing countries.

Phase 8 + post-Phase-8 audit pass: the 10 countries with the most NRA
student / scholar volume to the US (or with the most-cited treaty
articles) must remain ``verified_against_pub901=true``. If a future seed
regression flips one back to False, this test fails so we catch it
before release.

Also pins the specific Pub-901-derived values for each country so a
regression in caps, year limits, or article numbers is caught.
"""

from __future__ import annotations

from src.functions.treaty_evaluator import TreatyEvaluator

AUDITED = ["IN", "CN", "KR", "CA", "BD", "DE", "FR", "GB", "PK", "JP"]


def _articles_by_id(doc, article_id: str, category: str | None = None):
    matches = [a for a in doc.articles if a.article_id == article_id]
    if category is not None:
        matches = [a for a in matches if a.category == category]
    return matches


class TestAuditFlags:
    def setup_method(self):
        self.evaluator = TreatyEvaluator(tax_year=2025)

    def test_all_top10_verified(self):
        for iso2 in AUDITED:
            doc = self.evaluator.country(iso2)
            assert doc is not None, f"Missing {iso2}"
            assert doc.verified_against_pub901, (
                f"{iso2} ({doc.country_name}) regressed to "
                "verified_against_pub901=false — re-audit before release."
            )


class TestPinnedValues:
    """Lock in the specific article parameters caught during the audit."""

    def setup_method(self):
        self.evaluator = TreatyEvaluator(tax_year=2025)

    def test_china_three_articles(self):
        cn = self.evaluator.country("CN")
        ids = sorted(a.article_id for a in cn.articles)
        assert ids == ["19", "20(b)", "20(c)"]

    def test_china_20c_5k_cap_no_year_limit_saving_clause(self):
        cn = self.evaluator.country("CN")
        [art] = _articles_by_id(cn, "20(c)")
        assert art.max_dollar_cap == 5000.0
        assert art.max_year_cap is None
        assert art.saving_clause_exception is True

    def test_china_19_three_year_cap_no_saving_clause(self):
        cn = self.evaluator.country("CN")
        [art] = _articles_by_id(cn, "19")
        assert art.max_year_cap == 3
        assert art.saving_clause_exception is False

    def test_india_21_1_foreign_source_only(self):
        ind = self.evaluator.country("IN")
        [art] = _articles_by_id(ind, "21(1)", "scholarship_fellowship")
        assert art.source_restriction == "foreign_source_only"

    def test_india_21_2_no_dollar_cap(self):
        """Article 21(2) is the standard-deduction projection — no $ cap on wages."""
        ind = self.evaluator.country("IN")
        [art] = _articles_by_id(ind, "21(2)")
        assert art.max_dollar_cap is None

    def test_korea_21_1_2k_cap_5yr(self):
        kr = self.evaluator.country("KR")
        student_wage = [
            a for a in kr.articles if a.category == "student_personal_services"
        ]
        assert len(student_wage) == 1
        assert student_wage[0].max_dollar_cap == 2000.0
        assert student_wage[0].max_year_cap == 5

    def test_canada_foreign_source_only(self):
        ca = self.evaluator.country("CA")
        assert len(ca.articles) == 1
        assert ca.articles[0].article_id == "XX"
        assert ca.articles[0].source_restriction == "foreign_source_only"

    def test_bangladesh_21_2_8k_cap_2yr(self):
        bd = self.evaluator.country("BD")
        [art] = _articles_by_id(bd, "21(2)")
        assert art.max_dollar_cap == 8000.0
        assert art.max_year_cap == 2

    def test_germany_no_duplicate_visas(self):
        de = self.evaluator.country("DE")
        for art in de.articles:
            assert len(art.covered_visas) == len(set(art.covered_visas)), (
                f"DE {art.article_id} has duplicates: {art.covered_visas}"
            )

    def test_germany_20_4_9k_cap_4yr(self):
        de = self.evaluator.country("DE")
        [art] = _articles_by_id(de, "20(4)")
        assert art.max_dollar_cap == 9000.0
        assert art.max_year_cap == 4

    def test_france_21_1_5k_cap_5yr(self):
        fr = self.evaluator.country("FR")
        student_wage = [
            a for a in fr.articles if a.category == "student_personal_services"
        ]
        assert len(student_wage) == 1
        assert student_wage[0].max_dollar_cap == 5000.0
        assert student_wage[0].max_year_cap == 5

    def test_uk_article_id_is_20a(self):
        gb = self.evaluator.country("GB")
        assert len(gb.articles) == 1
        assert gb.articles[0].article_id == "20A"
        assert gb.articles[0].source_restriction == "foreign_source_only"
        assert gb.articles[0].max_dollar_cap is None  # No $9k cap (that's Germany)

    def test_pakistan_xiii_1_5k_no_year_limit(self):
        pk = self.evaluator.country("PK")
        wage_article = [
            a for a in pk.articles if a.category == "student_personal_services"
        ]
        assert len(wage_article) == 1
        assert wage_article[0].article_id == "XIII(1)"
        assert wage_article[0].max_dollar_cap == 5000.0
        assert wage_article[0].max_year_cap is None  # Pakistan is no-limit

    def test_japan_foreign_source_only(self):
        jp = self.evaluator.country("JP")
        assert len(jp.articles) == 1
        assert jp.articles[0].source_restriction == "foreign_source_only"
