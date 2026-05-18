#!/usr/bin/env python3
"""Audit script for the seeded treaty database.

Reports, per country, which article categories are covered, which articles
are flagged as needing Form 8833, and any countries whose
``verified_against_pub901`` flag is still False. Run before each release to
flag stale entries that need a human cross-check against the current Pub 901.

Usage::

    python -m scripts.audit_treaties
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from src.functions.treaty_evaluator import TreatyEvaluator


def main() -> int:
    evaluator = TreatyEvaluator(tax_year=2025)
    countries = evaluator.countries

    if not countries:
        print("No treaty files loaded.", file=sys.stderr)
        return 1

    print(f"Loaded {len(countries)} treaty files from {evaluator.treaties_dir}\n")

    category_counts: Counter[str] = Counter()
    unverified = []
    not_in_force = []
    countries_missing_student_wages = []

    for iso2, doc in sorted(countries.items()):
        if not doc.verified_against_pub901:
            unverified.append(iso2)
        if not doc.treaty_in_force:
            not_in_force.append(iso2)

        has_student_wages = False
        for article in doc.articles:
            category_counts[article.category] += 1
            if article.category in {"student_personal_services", "foreign_source_remittance"}:
                has_student_wages = True

        if doc.treaty_in_force and not has_student_wages:
            countries_missing_student_wages.append(iso2)

    print("Articles per category:")
    for category, n in category_counts.most_common():
        print(f"  {n:>3}  {category}")

    print()
    print(f"Treaty not in force ({len(not_in_force)}):", ", ".join(not_in_force) or "—")
    print(
        f"Countries with no student-wage article ({len(countries_missing_student_wages)}):",
        ", ".join(countries_missing_student_wages) or "—",
    )
    print(
        f"Unverified against Pub 901 ({len(unverified)}/{len(countries)}):",
        "all" if len(unverified) == len(countries) else ", ".join(unverified),
    )
    print()
    print(
        "NEXT STEPS: cross-reference each unverified country against the current "
        "IRS Publication 901 tables and set ``verified_against_pub901: true`` in "
        "the corresponding JSON file once confirmed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
