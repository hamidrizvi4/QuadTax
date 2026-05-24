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

# Countries audited in the second pass (the remaining 56). Combined with
# AUDITED above this covers every file in the database.
SECOND_PASS = [
    "AM", "AT", "AU", "AZ", "BB", "BE", "BG", "BY", "CH", "CY", "CZ", "DK",
    "EE", "EG", "ES", "FI", "GE", "GR", "HU", "ID", "IE", "IL", "IS", "IT",
    "JM", "KG", "KZ", "LK", "LT", "LU", "LV", "MA", "MD", "MT", "MX", "NL",
    "NO", "NZ", "PH", "PL", "PT", "RO", "RU", "SE", "SI", "SK", "TH", "TJ",
    "TM", "TN", "TR", "TT", "UA", "UZ", "VE", "ZA",
]

USSR_SUCCESSOR_STATES = ["AM", "AZ", "BY", "GE", "KG", "MD", "TJ", "TM", "UZ"]


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


class TestSecondPassAuditFlags:
    """The remaining 56 countries audited in the second pass must stay verified."""

    def setup_method(self):
        self.evaluator = TreatyEvaluator(tax_year=2025)

    def test_full_database_verified(self):
        """Every loaded country must carry verified_against_pub901=True."""
        unverified = [
            iso
            for iso, doc in self.evaluator.countries.items()
            if not doc.verified_against_pub901
        ]
        assert unverified == [], f"Unverified countries: {unverified}"

    def test_no_country_dropped_from_second_pass(self):
        for iso in SECOND_PASS:
            assert self.evaluator.country(iso) is not None, f"Missing {iso}"


class TestSecondPassPinnedValues:
    """Lock in specific values for the second-pass countries."""

    def setup_method(self):
        self.evaluator = TreatyEvaluator(tax_year=2025)

    # Tier A — $5,000 / 5 years
    def test_5k_5yr_tier_consistent(self):
        for iso in ("CZ", "EE", "LT", "LV", "PT", "SK", "SI", "ES", "VE"):
            doc = self.evaluator.country(iso)
            wage = [
                a
                for a in doc.articles
                if a.category == "student_personal_services" and a.max_dollar_cap == 5000.0
            ]
            assert wage, f"{iso}: missing $5,000 student-wage article"
            assert wage[0].max_year_cap == 5, f"{iso}: year cap is {wage[0].max_year_cap}, expected 5"

    # Tier B — $2,000 / 5 years (NL is the exception at 3 yrs)
    def test_2k_5yr_tier_consistent(self):
        for iso in ("CY", "ID", "JM", "MA", "NO", "PL", "RO", "TT"):
            doc = self.evaluator.country(iso)
            wage = [
                a
                for a in doc.articles
                if a.category == "student_personal_services" and a.max_dollar_cap == 2000.0
            ]
            assert wage, f"{iso}: missing $2,000 student-wage article"
            assert wage[0].max_year_cap == 5, f"{iso}: year cap is {wage[0].max_year_cap}, expected 5"

    def test_netherlands_uses_3yr_window(self):
        """NL is the only $2k country with a 3-year window (not 5)."""
        nl = self.evaluator.country("NL")
        [art] = _articles_by_id(nl, "22(2)")
        assert art.max_dollar_cap == 2000.0
        assert art.max_year_cap == 3

    # Tier C — assorted caps
    def test_belgium_bulgaria_9k_2yr(self):
        for iso in ("BE", "BG"):
            doc = self.evaluator.country(iso)
            wage = [
                a for a in doc.articles if a.category == "student_personal_services"
            ]
            assert wage[0].max_dollar_cap == 9000.0
            assert wage[0].max_year_cap == 2

    def test_denmark_8k_3yr(self):
        dk = self.evaluator.country("DK")
        [art] = _articles_by_id(dk, "19(1)")
        assert art.max_dollar_cap == 8000.0
        assert art.max_year_cap == 3

    def test_iceland_malta_9k_5yr(self):
        is_doc = self.evaluator.country("IS")
        [art] = _articles_by_id(is_doc, "19(1)")
        assert art.max_dollar_cap == 9000.0
        assert art.max_year_cap == 5

        mt = self.evaluator.country("MT")
        [art] = _articles_by_id(mt, "20")
        assert art.max_dollar_cap == 9000.0

    def test_sri_lanka_6k(self):
        lk = self.evaluator.country("LK")
        [art] = _articles_by_id(lk, "21(1)")
        assert art.max_dollar_cap == 6000.0

    def test_tunisia_4k(self):
        tn = self.evaluator.country("TN")
        [art] = _articles_by_id(tn, "20")
        assert art.max_dollar_cap == 4000.0

    def test_3k_tier(self):
        for iso in ("EG", "IL", "PH", "TH"):
            doc = self.evaluator.country(iso)
            wage = [
                a
                for a in doc.articles
                if a.category == "student_personal_services" and a.max_dollar_cap == 3000.0
            ]
            assert wage, f"{iso}: missing $3,000 student-wage article"
            assert wage[0].max_year_cap == 5

    # Tier D — foreign-source-only
    def test_foreign_source_only_tier(self):
        for iso in (
            "AT", "BB", "CH", "FI", "GR", "IE", "IT", "LU", "MX",
            "NZ", "SE", "TR", "ZA",
        ):
            doc = self.evaluator.country(iso)
            assert doc.articles, f"{iso}: zero articles seeded"
            for art in doc.articles:
                assert art.source_restriction == "foreign_source_only", (
                    f"{iso}: article {art.article_id} has {art.source_restriction}, "
                    "expected foreign_source_only"
                )

    def test_australia_has_no_articles(self):
        au = self.evaluator.country("AU")
        assert au.articles == []

    # Tier E — USSR successor states get TWO articles after audit fix
    def test_ussr_successors_have_us_source_article(self):
        """The audit added Article VI(1)(c) ($10,000 / 5 yr US-source wages)."""
        for iso in USSR_SUCCESSOR_STATES:
            doc = self.evaluator.country(iso)
            us_source_wage = [
                a
                for a in doc.articles
                if a.article_id == "VI(1)(c)"
                and a.category == "student_personal_services"
                and a.source_restriction == "us_source_only"
            ]
            assert us_source_wage, f"{iso}: missing Article VI(1)(c) US-source row"
            assert us_source_wage[0].max_dollar_cap == 10000.0
            assert us_source_wage[0].max_year_cap == 5

    def test_ussr_successors_still_have_foreign_source_article(self):
        """The original Article VI (foreign-source maintenance) must remain alongside."""
        for iso in USSR_SUCCESSOR_STATES:
            doc = self.evaluator.country(iso)
            foreign_source = [
                a for a in doc.articles
                if a.article_id == "VI" and a.source_restriction == "foreign_source_only"
            ]
            assert foreign_source, f"{iso}: missing original Article VI foreign-source row"

    # Tier F — not in force
    def test_hungary_and_russia_not_in_force(self):
        for iso in ("HU", "RU"):
            doc = self.evaluator.country(iso)
            assert doc.treaty_in_force is False, f"{iso}: should be treaty_in_force=False"
            assert doc.articles == [], f"{iso}: should have no active articles"
