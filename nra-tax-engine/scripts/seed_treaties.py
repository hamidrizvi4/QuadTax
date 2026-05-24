#!/usr/bin/env python3
"""Seed per-country treaty JSON files under database/tax_year/2025/treaties/.

This script encodes the US income-tax treaty parameters relevant to NRA filers
(students, researchers, trainees) drawn from IRS Pub 901 (Tables 2 and 3) and
the underlying treaty texts. Every article entry includes a ``pub901_table_ref``
for audit traceability and a ``note`` describing edge cases.

Run::

    python -m scripts.seed_treaties

The script is idempotent — it overwrites the existing JSON files. Each country
is marked ``verified_against_pub901: False`` until a human audit confirms the
articles against the current Pub 901 publication.

IMPORTANT: This is structured-data seeding, not authoritative interpretation.
A licensed preparer must verify each country against the live Pub 901 before
production release. The script is the canonical refresh tool.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.functions.treaty_schema import (
    SavingClause,
    TreatyArticle,
    TreatyDocument,
)

OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "database"
    / "tax_year"
    / "2025"
    / "treaties"
)


def article(
    article_id: str,
    category: str,
    *,
    covered_visas: Optional[List[str]] = None,
    max_dollar_cap: Optional[float] = None,
    max_year_cap: Optional[int] = None,
    year_counting_rule: str = "none",
    source_restriction: str = "any_source",
    saving_clause_exception: bool = False,
    saving_clause_exception_cite: Optional[str] = None,
    requires_form_8833_if_over: Optional[float] = 10000.0,
    notice_2010_21_exception: bool = False,
    pub901_table_ref: Optional[str] = None,
    note: Optional[str] = None,
) -> TreatyArticle:
    return TreatyArticle(
        article_id=article_id,
        category=category,  # type: ignore[arg-type]
        covered_visas=covered_visas or [],
        max_dollar_cap=max_dollar_cap,
        max_year_cap=max_year_cap,
        year_counting_rule=year_counting_rule,  # type: ignore[arg-type]
        source_restriction=source_restriction,  # type: ignore[arg-type]
        saving_clause_exception=saving_clause_exception,
        saving_clause_exception_cite=saving_clause_exception_cite,
        requires_form_8833_if_over=requires_form_8833_if_over,
        notice_2010_21_exception=notice_2010_21_exception,
        pub901_table_ref=pub901_table_ref,
        note=note,
    )


# ---------------------------------------------------------------------------
# Treaty data — per-country article lists
# ---------------------------------------------------------------------------
#
# Categories key:
#   scholarship_fellowship       Code 16 / fellowship & scholarship grant
#   student_personal_services    Wages earned by a student (US-source)
#   apprentice_trainee           Apprentice/business trainee (often separate article)
#   teaching_research            Visiting professor / researcher (Code 19)
#   foreign_source_remittance    UK/CA/JP-style — exempt only if income source is foreign
#
# Standard 5-yr student visa rule typically applies; per-country deviations noted.

STUDENT_VISAS = ["F-1", "J-1", "M-1", "Q-1"]
TEACHER_VISAS = ["J-1", "H-1B"]

TREATIES: Dict[str, dict] = {
    # =====================================================================
    # Tier 1 — Highest-volume student source countries
    # =====================================================================
    "CN": {
        "country_name": "China (People's Republic of)",
        "treaty_effective_date": "1987-01-01",
        "saving_clause": {
            "exists": True,
            "cite": "Article 23(1)",
            "exception_paragraph": "Protocol paragraph 2 preserves Article 20 benefits for individuals "
            "even after they become US residents.",
        },
        "articles": [
            article(
                "19",
                "teaching_research",
                covered_visas=TEACHER_VISAS,
                max_dollar_cap=None,
                max_year_cap=3,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                saving_clause_exception=False,
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, China, row 'Teaching / Research'",
                note="Article 19 covers visiting professors/researchers for up to 3 years from first arrival. "
                "Once the 3-year window closes, the article does NOT apply retroactively.",
            ),
            article(
                "20(b)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=None,
                year_counting_rule="none",
                source_restriction="any_source",
                saving_clause_exception=True,
                saving_clause_exception_cite="US-China Protocol paragraph 2",
                requires_form_8833_if_over=10000.0,
                pub901_table_ref="Table 3, China",
                note="Scholarship/fellowship from any source — unlimited duration, survives saving clause.",
            ),
            article(
                "20(c)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=None,
                year_counting_rule="none",
                source_restriction="us_source_only",
                saving_clause_exception=True,
                saving_clause_exception_cite="US-China Protocol paragraph 2",
                requires_form_8833_if_over=0.0,
                notice_2010_21_exception=False,
                pub901_table_ref="Table 2, China",
                note="$5,000/yr cap on student wages; no year limit; survives saving clause. "
                "Form 8833 generally required by IRS practice even though under $10k.",
            ),
        ],
        "notes": [
            "China treaty applies to mainland PRC only; does not cover Hong Kong or Taiwan.",
        ],
    },
    "IN": {
        "country_name": "India",
        "treaty_effective_date": "1991-01-01",
        "saving_clause": {
            "exists": True,
            "cite": "Article 1(3)",
            "exception_paragraph": "Article 1(4)(b) preserves Article 21 benefits for students.",
        },
        "articles": [
            article(
                "21(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=None,
                source_restriction="foreign_source_only",
                saving_clause_exception=True,
                saving_clause_exception_cite="Article 1(4)(b)",
                requires_form_8833_if_over=10000.0,
                pub901_table_ref="Table 3, India",
                note="ONLY foreign-source scholarships are exempt — US-university-funded scholarships "
                "are NOT exempt under this article (common error). Saving clause exception preserved.",
            ),
            article(
                "21(2)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,  # Standard deduction equivalent — not a dollar cap on income
                max_year_cap=None,
                source_restriction="any_source",
                saving_clause_exception=True,
                saving_clause_exception_cite="Article 1(4)(b)",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, India, special note on standard deduction",
                note="UNIQUE: India is the only treaty country where students may claim the federal "
                "single standard deduction. Implementation: TaxCalculator subtracts the single-status "
                "standard deduction from ECI when this article is applied. NOT a wage exemption.",
            ),
        ],
        "notes": [
            "Per US Treasury technical explanation, Article 21(2) is interpreted to allow Indian "
            "students/business apprentices to claim the same standard deduction as US single filers.",
        ],
    },
    "KR": {
        "country_name": "Korea, Republic of",
        "treaty_effective_date": "1979-10-20",
        "saving_clause": {
            "exists": True,
            "cite": "Article 4(4)",
            "exception_paragraph": "Article 21 benefits preserved for non-citizens.",
        },
        "articles": [
            article(
                "21(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                saving_clause_exception=True,
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Korea",
                note="$2,000/yr student wage exemption, max 5 years.",
            ),
            article(
                "21(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="any_source",
                saving_clause_exception=True,
                pub901_table_ref="Table 3, Korea",
                note="Scholarships also covered by Article 21(1); 5-year maximum applies.",
            ),
        ],
    },
    "DE": {
        "country_name": "Germany",
        "treaty_effective_date": "1989-08-21",
        "saving_clause": {
            "exists": True,
            "cite": "Article 1(4)",
            "exception_paragraph": "Article 20 benefits preserved for residents temporarily in US.",
        },
        "articles": [
            article(
                "20(4)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS + ["J-1"],
                max_dollar_cap=9000.0,
                max_year_cap=4,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Germany",
                note="$9,000/yr study & training compensation, max 4 years from arrival.",
            ),
            article(
                "20(2)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS + ["J-1"],
                max_dollar_cap=None,
                max_year_cap=None,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 3, Germany",
                note="Foreign-source scholarship/fellowship grants exempt.",
            ),
        ],
    },
    "GB": {
        "country_name": "United Kingdom",
        "treaty_effective_date": "2003-03-31",
        "saving_clause": {
            "exists": True,
            "cite": "Article 1(4)",
            "exception_paragraph": "Article 20 benefits preserved for visiting students.",
        },
        "articles": [
            article(
                "20A",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=None,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, UK",
                note="UK treaty exempts foreign-source maintenance/education payments only. "
                "US-source wages NOT exempt. No $9k cap (that's Germany).",
            ),
        ],
    },
    "CA": {
        "country_name": "Canada",
        "treaty_effective_date": "1980-09-26",
        "saving_clause": {
            "exists": True,
            "cite": "Article XXIX(2)",
            "exception_paragraph": "Article XX preserved for visiting students.",
        },
        "articles": [
            article(
                "XX",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Canada",
                note="Canadian treaty exempts foreign-source maintenance/education payments to "
                "students/trainees. US-source wages not exempt under this article.",
            ),
        ],
    },
    "PK": {
        "country_name": "Pakistan",
        "treaty_effective_date": "1959-07-01",
        "saving_clause": {"exists": True, "cite": "Article II(2)"},
        "articles": [
            article(
                "XIII(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=None,
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Pakistan",
                note="$5,000 student wage exemption, no year limit. Pakistan treaty is one of the "
                "oldest US treaties (1957/59).",
            ),
            article(
                "XIII(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 3, Pakistan",
            ),
        ],
    },
    "JP": {
        "country_name": "Japan",
        "treaty_effective_date": "2004-03-30",
        "saving_clause": {
            "exists": True,
            "cite": "Article 1(4)",
            "exception_paragraph": "Article 20 benefits preserved for visiting students.",
        },
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=None,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Japan",
                note="Japan treaty (2004 protocol) exempts foreign-source maintenance/education only.",
            ),
        ],
    },
    "MX": {
        "country_name": "Mexico",
        "treaty_effective_date": "1993-12-28",
        "saving_clause": {"exists": True, "cite": "Article 1(4)"},
        "articles": [
            article(
                "21",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Mexico",
                note="Mexico treaty exempts foreign-source remittances only. No US-source wage exemption.",
            ),
        ],
    },
    "ES": {
        "country_name": "Spain",
        "treaty_effective_date": "1990-12-21",
        "saving_clause": {"exists": True, "cite": "Article 1(3)"},
        "articles": [
            article(
                "22(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Spain",
                note="$5,000/yr student wages, max 5 years.",
            ),
            article(
                "22(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=5,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Spain",
            ),
        ],
    },
    "FR": {
        "country_name": "France",
        "treaty_effective_date": "1994-08-31",
        "saving_clause": {"exists": True, "cite": "Article 29(2)"},
        "articles": [
            article(
                "21(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, France",
            ),
            article(
                "21(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, France",
            ),
        ],
    },
    "ID": {
        "country_name": "Indonesia",
        "treaty_effective_date": "1990-02-01",
        "saving_clause": {"exists": True, "cite": "Article 26(2)"},
        "articles": [
            article(
                "19(1)(b)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Indonesia",
            ),
            article(
                "19(1)(a)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Indonesia",
            ),
        ],
    },
    "NL": {
        "country_name": "Netherlands",
        "treaty_effective_date": "1993-12-31",
        "saving_clause": {"exists": True, "cite": "Article 24(1)"},
        "articles": [
            article(
                "22(2)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=3,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Netherlands",
                note="3-year limit, $2,000 cap.",
            ),
            article(
                "22(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Netherlands",
            ),
        ],
    },
    # =====================================================================
    # Tier 2 — Other treaty partners with student provisions
    # =====================================================================
    "BD": {
        "country_name": "Bangladesh",
        "treaty_effective_date": "2006-08-07",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "21(2)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=8000.0,
                max_year_cap=2,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Bangladesh",
                note="$8,000/yr, max 2 years.",
            ),
            article(
                "21(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Bangladesh",
            ),
        ],
    },
    "BE": {
        "country_name": "Belgium",
        "treaty_effective_date": "2008-01-01",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "19(1)(b)(ii)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=9000.0,
                max_year_cap=2,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Belgium",
            ),
            article(
                "19(1)(a)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Belgium",
            ),
        ],
    },
    "BG": {
        "country_name": "Bulgaria",
        "treaty_effective_date": "2009-01-01",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "19(1)(b)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=9000.0,
                max_year_cap=2,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Bulgaria",
            ),
            article(
                "19(1)(a)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Bulgaria",
            ),
        ],
    },
    "CY": {
        "country_name": "Cyprus",
        "treaty_effective_date": "1984-12-31",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "21(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Cyprus",
            ),
        ],
    },
    "CZ": {
        "country_name": "Czech Republic",
        "treaty_effective_date": "1993-12-23",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "21(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Czech Republic",
            ),
            article(
                "21(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Czech Republic",
            ),
        ],
    },
    "DK": {
        "country_name": "Denmark",
        "treaty_effective_date": "2001-03-31",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "19(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=8000.0,
                max_year_cap=3,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Denmark",
            ),
        ],
    },
    "EG": {
        "country_name": "Egypt",
        "treaty_effective_date": "1980-12-31",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "23(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=3000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Egypt",
            ),
            article(
                "23(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Egypt",
            ),
        ],
    },
    "EE": {
        "country_name": "Estonia",
        "treaty_effective_date": "1998-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20(1)(b)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Estonia",
            ),
        ],
    },
    "GR": {
        "country_name": "Greece",
        "treaty_effective_date": "1953-12-30",
        "saving_clause": {"exists": False},  # Old treaty, no saving clause
        "articles": [
            article(
                "XII",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=None,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Greece",
                note="Older 1950s treaty — only foreign-source remittances covered.",
            ),
        ],
    },
    "IS": {
        "country_name": "Iceland",
        "treaty_effective_date": "2008-12-15",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "19(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=9000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Iceland",
            ),
        ],
    },
    "IL": {
        "country_name": "Israel",
        "treaty_effective_date": "1995-01-01",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "24(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=3000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Israel",
            ),
            article(
                "24(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Israel",
            ),
        ],
    },
    "JM": {
        "country_name": "Jamaica",
        "treaty_effective_date": "1981-12-29",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "21(2)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Jamaica",
            ),
        ],
    },
    "KZ": {
        "country_name": "Kazakhstan",
        "treaty_effective_date": "1996-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "19",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, Kazakhstan",
                note="Foreign-source maintenance/education only.",
            ),
        ],
    },
    "LV": {
        "country_name": "Latvia",
        "treaty_effective_date": "1999-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20(1)(b)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Latvia",
            ),
        ],
    },
    "LT": {
        "country_name": "Lithuania",
        "treaty_effective_date": "1999-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20(1)(b)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Lithuania",
            ),
        ],
    },
    "MA": {
        "country_name": "Morocco",
        "treaty_effective_date": "1981-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "18",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Morocco",
            ),
        ],
    },
    "MT": {
        "country_name": "Malta",
        "treaty_effective_date": "2010-11-23",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=9000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Malta",
            ),
        ],
    },
    "NO": {
        "country_name": "Norway",
        "treaty_effective_date": "1972-11-29",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "16(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Norway",
            ),
        ],
    },
    "PH": {
        "country_name": "Philippines",
        "treaty_effective_date": "1982-10-16",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "22(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=3000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Philippines",
            ),
            article(
                "22(1)",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Philippines",
            ),
        ],
    },
    "PL": {
        "country_name": "Poland",
        "treaty_effective_date": "1974-07-23",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "18(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Poland",
            ),
        ],
    },
    "PT": {
        "country_name": "Portugal",
        "treaty_effective_date": "1995-12-18",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "23(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Portugal",
            ),
        ],
    },
    "RO": {
        "country_name": "Romania",
        "treaty_effective_date": "1973-12-04",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Romania",
            ),
        ],
    },
    "SK": {
        "country_name": "Slovak Republic",
        "treaty_effective_date": "1993-12-31",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "21(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Slovak Republic",
            ),
        ],
    },
    "SI": {
        "country_name": "Slovenia",
        "treaty_effective_date": "2001-06-22",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20(1)(b)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Slovenia",
            ),
        ],
    },
    "LK": {
        "country_name": "Sri Lanka",
        "treaty_effective_date": "2003-07-12",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "21(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=6000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Sri Lanka",
            ),
        ],
    },
    "TH": {
        "country_name": "Thailand",
        "treaty_effective_date": "1997-12-15",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "22",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=3000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Thailand",
            ),
            article(
                "22",
                "scholarship_fellowship",
                covered_visas=STUDENT_VISAS,
                source_restriction="any_source",
                pub901_table_ref="Table 3, Thailand",
            ),
        ],
    },
    "TT": {
        "country_name": "Trinidad and Tobago",
        "treaty_effective_date": "1970-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "19",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=2000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Trinidad and Tobago",
            ),
        ],
    },
    "TN": {
        "country_name": "Tunisia",
        "treaty_effective_date": "1990-02-26",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=4000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Tunisia",
            ),
        ],
    },
    "UA": {
        "country_name": "Ukraine",
        "treaty_effective_date": "2000-06-05",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=None,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, Ukraine",
                note="Foreign-source maintenance/education only.",
            ),
        ],
    },
    "VE": {
        "country_name": "Venezuela",
        "treaty_effective_date": "2000-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "21(1)",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=5000.0,
                max_year_cap=5,
                year_counting_rule="from_first_arrival",
                source_restriction="us_source_only",
                requires_form_8833_if_over=0.0,
                pub901_table_ref="Table 2, Venezuela",
            ),
        ],
    },
    # =====================================================================
    # Tier 3 — Treaty in force but limited/no student-specific provisions
    # =====================================================================
    "AU": {
        "country_name": "Australia",
        "treaty_effective_date": "1983-10-31",
        "saving_clause": {"exists": True},
        "articles": [],
        "notes": [
            "Australia treaty does not provide a student wage exemption. "
            "Students may still claim §117 qualified-scholarship exclusion (statutory, not treaty).",
        ],
    },
    "AT": {
        "country_name": "Austria",
        "treaty_effective_date": "1998-02-01",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Austria",
            ),
        ],
    },
    "CH": {
        "country_name": "Switzerland",
        "treaty_effective_date": "1997-12-19",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Switzerland",
            ),
        ],
    },
    "FI": {
        "country_name": "Finland",
        "treaty_effective_date": "1990-12-30",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Finland",
            ),
        ],
    },
    "IE": {
        "country_name": "Ireland",
        "treaty_effective_date": "1997-12-17",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Ireland",
            ),
        ],
    },
    "IT": {
        "country_name": "Italy",
        "treaty_effective_date": "2009-12-16",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Italy",
            ),
        ],
    },
    "LU": {
        "country_name": "Luxembourg",
        "treaty_effective_date": "2001-01-01",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Luxembourg",
            ),
        ],
    },
    "NZ": {
        "country_name": "New Zealand",
        "treaty_effective_date": "1983-11-02",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, New Zealand",
            ),
        ],
    },
    "SE": {
        "country_name": "Sweden",
        "treaty_effective_date": "1995-10-26",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Sweden",
            ),
        ],
    },
    "TR": {
        "country_name": "Turkey",
        "treaty_effective_date": "1997-12-19",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Turkey",
            ),
        ],
    },
    "ZA": {
        "country_name": "South Africa",
        "treaty_effective_date": "1997-12-28",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, South Africa",
            ),
        ],
    },
    "BB": {
        "country_name": "Barbados",
        "treaty_effective_date": "1986-02-28",
        "saving_clause": {"exists": True},
        "articles": [
            article(
                "20",
                "foreign_source_remittance",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2/3, Barbados",
            ),
        ],
    },
    # =====================================================================
    # Tier 4 — USSR successor states (1973 USSR treaty still applies)
    # =====================================================================
    "AM": {
        "country_name": "Armenia",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                max_dollar_cap=None,
                max_year_cap=5,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
                note="USSR 1973 treaty applies to Armenia as successor state.",
            ),
        ],
    },
    "AZ": {
        "country_name": "Azerbaijan",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    "BY": {
        "country_name": "Belarus",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    "GE": {
        "country_name": "Georgia",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    "KG": {
        "country_name": "Kyrgyzstan",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    "MD": {
        "country_name": "Moldova",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    "TJ": {
        "country_name": "Tajikistan",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    "TM": {
        "country_name": "Turkmenistan",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    "UZ": {
        "country_name": "Uzbekistan",
        "treaty_effective_date": "1976-01-01",
        "saving_clause": {"exists": False},
        "articles": [
            article(
                "VI",
                "student_personal_services",
                covered_visas=STUDENT_VISAS,
                source_restriction="foreign_source_only",
                pub901_table_ref="Table 2, USSR successor states",
            ),
        ],
    },
    # =====================================================================
    # Tier 5 — Treaty terminated or suspended
    # =====================================================================
    "HU": {
        "country_name": "Hungary",
        "treaty_in_force": False,
        "treaty_effective_date": None,
        "saving_clause": {"exists": False},
        "articles": [],
        "notes": [
            "TREATY TERMINATED. US Treasury notified Hungary on July 8, 2022; "
            "treaty ceased to have effect for withholding taxes on January 1, 2024, "
            "and for other taxes for periods beginning on/after January 1, 2024. "
            "No treaty benefits for TY2024+. Hungarian students must follow default NRA rules.",
        ],
    },
    "RU": {
        "country_name": "Russia",
        "treaty_in_force": False,
        "treaty_effective_date": "1992-12-16",
        "saving_clause": {"exists": True},
        "articles": [],
        "notes": [
            "TREATY SUSPENDED. Russia notified the US in 2023 of partial suspension; "
            "the US Treasury announced on June 17, 2024 that Articles 1, 5-21, and 23 "
            "are suspended by mutual agreement beginning August 16, 2024. "
            "For TY2025, treat as no benefits available for new claims.",
        ],
    },
}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for iso2, data in TREATIES.items():
        sc_data = data.get("saving_clause") or {}
        doc = TreatyDocument(
            country_name=data["country_name"],
            iso2=iso2,
            treaty_in_force=data.get("treaty_in_force", True),
            treaty_effective_date=data.get("treaty_effective_date"),
            saving_clause=SavingClause(**sc_data),
            articles=data.get("articles", []),
            notes=data.get("notes", []),
            verified_against_pub901=False,
        )
        path = OUTPUT_DIR / f"{iso2}.json"
        path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        written.append(iso2)

    print(f"Wrote {len(written)} treaty files to {OUTPUT_DIR}")
    print("ISO codes:", ", ".join(sorted(written)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
