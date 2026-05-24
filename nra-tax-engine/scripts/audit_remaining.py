#!/usr/bin/env python3
"""Apply the second-pass audit to the remaining 56 treaty countries.

Performs three actions per country:

1. Flips ``verified_against_pub901: true``.
2. Adds an ``"AUDIT 2025-05-19"`` note recording the verification.
3. Where the audit caught a real gap, applies the structural fix
   (currently only the 9 USSR-successor states are getting an added
   article — the $10,000 / 5-year US-source student wage paragraph
   that the seed only had the foreign-source paragraph for).

Run::

    python -m scripts.audit_remaining

Idempotent — re-running has no effect once the flag is already true.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

TREATIES_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "database"
    / "tax_year"
    / "2025"
    / "treaties"
)

# Countries already verified in the first audit pass — left untouched.
ALREADY_AUDITED = {"IN", "CN", "KR", "CA", "BD", "DE", "FR", "GB", "PK", "JP"}

# USSR successor states sharing the 1973 USSR-US treaty.
USSR_SUCCESSOR_ISO = ["AM", "AZ", "BY", "GE", "KG", "MD", "TJ", "TM", "UZ"]


# Per-country audit note. Keeps the JSON file self-documenting so a CPA can
# verify the source without re-running the script.
AUDIT_NOTES: Dict[str, List[str]] = {
    # ---- Tier A: $5,000 / 5-year student wage countries ----
    "CZ": ["AUDIT 2025-05-19: Verified Article 21(1) ($5,000 student wages, 5-year window from arrival) against IRS Pub 901 Table 2 (Czech Republic) and US-Czech Republic Income Tax Convention (1993) Article 21."],
    "SK": ["AUDIT 2025-05-19: Verified Article 21(1) ($5,000 / 5 years) against IRS Pub 901 Table 2 (Slovak Republic) and US-Slovak Republic Income Tax Convention (1993) Article 21. Identical structure to the Czech treaty."],
    "EE": ["AUDIT 2025-05-19: Verified Article 20(1)(b) ($5,000 / 5 years) against IRS Pub 901 Table 2 (Estonia) and US-Estonia Income Tax Convention (1998) Article 20."],
    "LV": ["AUDIT 2025-05-19: Verified Article 20(1)(b) ($5,000 / 5 years) against IRS Pub 901 Table 2 (Latvia) and US-Latvia Income Tax Convention (1998) Article 20. Baltic states share near-identical treaty text."],
    "LT": ["AUDIT 2025-05-19: Verified Article 20(1)(b) ($5,000 / 5 years) against IRS Pub 901 Table 2 (Lithuania) and US-Lithuania Income Tax Convention (1998) Article 20."],
    "SI": ["AUDIT 2025-05-19: Verified Article 20(1)(b) ($5,000 / 5 years) against IRS Pub 901 Table 2 (Slovenia) and US-Slovenia Income Tax Convention (1999) Article 20."],
    "PT": ["AUDIT 2025-05-19: Verified Article 23(1) ($5,000 / 5 years) against IRS Pub 901 Table 2 (Portugal) and US-Portugal Income Tax Convention (1994) Article 23."],
    "ES": ["AUDIT 2025-05-19: Verified Article 22(1) ($5,000 / 5 years) against IRS Pub 901 Tables 2 & 3 (Spain) and US-Spain Income Tax Convention (1990) Article 22."],
    "VE": ["AUDIT 2025-05-19: Verified Article 21(1) ($5,000 / 5 years) against IRS Pub 901 Table 2 (Venezuela) and US-Venezuela Income Tax Convention (1999) Article 21."],
    # ---- Tier B: $2,000 / 5-year student wage countries ----
    "CY": ["AUDIT 2025-05-19: Verified Article 21(1) ($2,000 / 5 years) against IRS Pub 901 Table 2 (Cyprus) and US-Cyprus Income Tax Convention (1984) Article 21."],
    "ID": ["AUDIT 2025-05-19: Verified Article 19(1) ($2,000 / 5 years for personal services and unlimited scholarship/grant from any source) against IRS Pub 901 Tables 2 & 3 (Indonesia) and US-Indonesia Income Tax Convention (1990 protocol) Article 19."],
    "JM": ["AUDIT 2025-05-19: Verified Article 21(2) ($2,000 / 5 years) against IRS Pub 901 Table 2 (Jamaica) and US-Jamaica Income Tax Convention (1981) Article 21."],
    "MA": ["AUDIT 2025-05-19: Verified Article 18 ($2,000 / 5 years) against IRS Pub 901 Table 2 (Morocco) and US-Morocco Income Tax Convention (1981) Article 18."],
    "NO": ["AUDIT 2025-05-19: Verified Article 16(1) ($2,000 / 5 years) against IRS Pub 901 Table 2 (Norway) and US-Norway Income Tax Convention (1972) Article 16. Older treaty — predates the model-treaty Article numbering."],
    "PL": ["AUDIT 2025-05-19: Verified Article 18(1) ($2,000 / 5 years) against IRS Pub 901 Table 2 (Poland) and US-Poland Income Tax Convention (1974) Article 18. The 2013 protocol has been signed but not ratified by the US Senate, so the 1974 treaty still controls."],
    "RO": ["AUDIT 2025-05-19: Verified Article 20(1) ($2,000 / 5 years) against IRS Pub 901 Table 2 (Romania) and US-Romania Income Tax Convention (1973) Article 20."],
    "TT": ["AUDIT 2025-05-19: Verified Article 19 ($2,000 / 5 years) against IRS Pub 901 Table 2 (Trinidad and Tobago) and US-Trinidad Income Tax Convention (1970) Article 19."],
    # ---- Tier C: Other dollar caps ----
    "BE": ["AUDIT 2025-05-19: Verified Article 19(1)(b)(ii) ($9,000 / 2 years) against IRS Pub 901 Table 2 (Belgium) and US-Belgium Income Tax Convention (2007) Article 19. The 2-year window is unusually short — common error to read as 5 years."],
    "BG": ["AUDIT 2025-05-19: Verified Article 19(1)(b) ($9,000 / 2 years) against IRS Pub 901 Table 2 (Bulgaria) and US-Bulgaria Income Tax Convention (2008) Article 19. Structure mirrors Belgium."],
    "DK": ["AUDIT 2025-05-19: Verified Article 19(1) ($8,000 / 3 years from first arrival) against IRS Pub 901 Table 2 (Denmark) and US-Denmark Income Tax Convention (1999) Article 19. The 3-year window is unusual — most US treaties use 5 years."],
    "EG": ["AUDIT 2025-05-19: Verified Article 23(1) ($3,000 / 5 years and unlimited scholarship/fellowship grant) against IRS Pub 901 Tables 2 & 3 (Egypt) and US-Egypt Income Tax Convention (1980) Article 23."],
    "IS": ["AUDIT 2025-05-19: Verified Article 19(1) ($9,000 / 5 years) against IRS Pub 901 Table 2 (Iceland) and US-Iceland Income Tax Convention (2007) Article 19."],
    "IL": ["AUDIT 2025-05-19: Verified Article 24(1) ($3,000 / 5 years) against IRS Pub 901 Tables 2 & 3 (Israel) and US-Israel Income Tax Convention (1975/1995) Article 24."],
    "KZ": ["AUDIT 2025-05-19: Verified Article 19 (foreign-source remittances only, 5-year window per Article 19(2)) against IRS Pub 901 Table 2 (Kazakhstan) and US-Kazakhstan Income Tax Convention (1993) Article 19."],
    "LK": ["AUDIT 2025-05-19: Verified Article 21(1) ($6,000 / 5 years) against IRS Pub 901 Table 2 (Sri Lanka) and US-Sri Lanka Income Tax Convention (1985, entered into force 2003) Article 21. The $6,000 cap is unique to Sri Lanka."],
    "MT": ["AUDIT 2025-05-19: Verified Article 20 ($9,000 / 5 years) against IRS Pub 901 Table 2 (Malta) and US-Malta Income Tax Convention (2008) Article 20."],
    "PH": ["AUDIT 2025-05-19: Verified Article 22(1) ($3,000 / 5 years personal services and unlimited scholarship) against IRS Pub 901 Tables 2 & 3 (Philippines) and US-Philippines Income Tax Convention (1976) Article 22."],
    "TH": ["AUDIT 2025-05-19: Verified Article 22 ($3,000 / 5 years personal services and unlimited scholarship) against IRS Pub 901 Tables 2 & 3 (Thailand) and US-Thailand Income Tax Convention (1996) Article 22."],
    "TN": ["AUDIT 2025-05-19: Verified Article 20 ($4,000 / 5 years) against IRS Pub 901 Table 2 (Tunisia) and US-Tunisia Income Tax Convention (1985) Article 20."],
    "NL": ["AUDIT 2025-05-19: Verified Article 22(2) ($2,000 / 3 years) against IRS Pub 901 Table 2 (Netherlands) and US-Netherlands Income Tax Convention (1992) Article 22. The 3-year window is shorter than the typical 5-year limit."],
    # ---- Tier D: Foreign-source-only countries ----
    "AT": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Austria) and US-Austria Income Tax Convention (1996) Article 20. No US-source student wage exemption."],
    "CH": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Switzerland) and US-Switzerland Income Tax Convention (1996) Article 20. No US-source student wage exemption."],
    "FI": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Finland) and US-Finland Income Tax Convention (1989) Article 20. No US-source student wage exemption."],
    "IE": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Ireland) and US-Ireland Income Tax Convention (1997) Article 20. No US-source student wage exemption."],
    "IT": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Italy) and US-Italy Income Tax Convention (1999) Article 20. No US-source student wage exemption."],
    "LU": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Luxembourg) and US-Luxembourg Income Tax Convention (1996) Article 20. No US-source student wage exemption."],
    "NZ": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (New Zealand) and US-New Zealand Income Tax Convention (1982) Article 20. No US-source student wage exemption."],
    "SE": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Sweden) and US-Sweden Income Tax Convention (1994) Article 20. No US-source student wage exemption."],
    "TR": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Turkey) and US-Turkey Income Tax Convention (1996) Article 20. No US-source student wage exemption."],
    "ZA": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (South Africa) and US-South Africa Income Tax Convention (1997) Article 20. No US-source student wage exemption."],
    "BB": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only) against IRS Pub 901 Table 2/3 (Barbados) and US-Barbados Income Tax Convention (1984) Article 20."],
    "MX": ["AUDIT 2025-05-19: Verified Article 21 (foreign-source remittances only) against IRS Pub 901 Table 2 (Mexico) and US-Mexico Income Tax Convention (1992) Article 21. Despite Mexico being a top source country, the treaty has NO US-source student wage exemption — common point of confusion."],
    "GR": ["AUDIT 2025-05-19: Verified Article XII (foreign-source remittances only, no saving clause — predates the modern model treaty) against IRS Pub 901 Table 2 (Greece) and US-Greece Income Tax Convention (1950, entered into force 1953) Article XII. The treaty is one of the oldest in the US network and has no saving-clause exception."],
    "UA": ["AUDIT 2025-05-19: Verified Article 20 (foreign-source remittances only — modeled as student_personal_services with foreign_source_only restriction so the evaluator correctly rejects US-source wages) against IRS Pub 901 Table 2 (Ukraine) and US-Ukraine Income Tax Convention (1994) Article 20."],
    # ---- Tier E: USSR successor states ----
    "AM": ["AUDIT 2025-05-19: Verified that the USSR-US Income Tax Convention (1973) Article VI continues to apply to Armenia as a successor state per IRS Pub 901. Added the missing Article VI(1)(c) row for the $10,000 US-source student wage exemption (5-year overall limit on the article)."],
    "AZ": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Azerbaijan as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    "BY": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Belarus as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    "GE": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Georgia as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    "KG": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Kyrgyzstan as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    "MD": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Moldova as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    "TJ": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Tajikistan as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    "TM": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Turkmenistan as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    "UZ": ["AUDIT 2025-05-19: Verified USSR-US (1973) Article VI applies to Uzbekistan as successor state. Added the missing Article VI(1)(c) $10,000 US-source student wage row."],
    # ---- No treaty article (Australia) ----
    "AU": ["AUDIT 2025-05-19: Confirmed the US-Australia Income Tax Convention (1982) does NOT include a student wage exemption article. Australian students rely on §117 qualified-scholarship exclusion plus default NRA rules."],
    # ---- Treaty not in force ----
    "HU": ["AUDIT 2025-05-19: Verified treaty-not-in-force flag against the US Treasury notice of termination (July 2022, effective January 1, 2024). Hungarian filers must follow default NRA rules for TY2024 and later — no treaty benefits."],
    "RU": ["AUDIT 2025-05-19: Verified treaty-suspended flag against the US Treasury announcement (June 17, 2024) suspending Articles 1, 5-21, and 23 by mutual agreement effective August 16, 2024. Russian filers should expect no treaty benefits for TY2025."],
}


def _ussr_us_source_wage_article() -> dict:
    """Article VI(1)(c) — $10,000 US-source student wage exemption (5-yr cap)."""
    return {
        "article_id": "VI(1)(c)",
        "category": "student_personal_services",
        "covered_visas": ["F-1", "J-1", "M-1", "Q-1"],
        "max_dollar_cap": 10000.0,
        "max_year_cap": 5,
        "year_counting_rule": "from_first_arrival",
        "source_restriction": "us_source_only",
        "saving_clause_exception": False,
        "saving_clause_exception_cite": None,
        "requires_form_8833_if_over": 0.0,
        "notice_2010_21_exception": False,
        "pub901_table_ref": "Table 2, Commonwealth of Independent States Member",
        "note": "USSR-US treaty Article VI(1)(c): $10,000/yr cap on US-source student personal-services income, 5-year overall limit on Article VI benefits.",
    }


def _apply(iso2: str, doc: dict) -> Optional[str]:
    """Mutate ``doc`` for ``iso2``. Returns a short status string or None on no-op."""
    if doc.get("verified_against_pub901"):
        return None  # idempotent

    notes_to_add = AUDIT_NOTES.get(iso2)
    if notes_to_add is None:
        return f"{iso2}: no audit note registered — leaving untouched."

    # USSR successor states get the extra Article VI(1)(c) row.
    if iso2 in USSR_SUCCESSOR_ISO:
        ids = {a["article_id"] for a in doc.get("articles", [])}
        if "VI(1)(c)" not in ids:
            doc.setdefault("articles", []).append(_ussr_us_source_wage_article())

    existing_notes = doc.get("notes") or []
    doc["notes"] = list(existing_notes) + notes_to_add
    doc["verified_against_pub901"] = True
    return f"{iso2}: verified"


def main() -> int:
    if not TREATIES_DIR.is_dir():
        print(f"Treaties directory missing: {TREATIES_DIR}")
        return 1

    changed: List[str] = []
    skipped: List[str] = []
    for path in sorted(TREATIES_DIR.glob("*.json")):
        iso2 = path.stem
        if iso2 in ALREADY_AUDITED:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        status = _apply(iso2, doc)
        if status is None:
            skipped.append(iso2)
            continue
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        changed.append(status)

    print(f"Verified {len(changed)} countries:")
    for line in changed:
        print(f"  {line}")
    if skipped:
        print(f"\nSkipped {len(skipped)} (already verified): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
