"""Form 8833 — Treaty-Based Return Position Disclosure (IRC §6114).

One Form 8833 is generated per qualifying treaty benefit. The populator
returns a list of per-benefit field maps in ``rows``; the PDF writer
clones the template N times and fills each clone from the corresponding
row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    rows: List[dict] = []

    for benefit in state.treaty.applied_benefits:
        if not benefit.get("requires_form_8833"):
            continue
        rows.append(
            {
                "box_1a_name": f"{ident.first_name} {ident.last_name}".strip(),
                "box_1b_tin": ident.primary_tin,
                "box_2_treaty_country": benefit.get("country_name", ""),
                "box_3_treaty_article": benefit.get("article_id", ""),
                "box_4_irc_provision_overridden": _irc_for_category(benefit.get("category", "")),
                "box_5_explanation": benefit.get("explanation", ""),
                "box_6_amount_exempted": float(benefit.get("exempt_amount", 0.0)),
                "saving_clause_exception_cite": (
                    "Applies despite saving clause; see treaty protocol."
                    if benefit.get("applies_after_saving_clause")
                    else ""
                ),
            }
        )

    return {
        "rows": rows,
        "count": len(rows),
        "filer_name": f"{ident.first_name} {ident.last_name}".strip(),
        "filer_tin": ident.primary_tin,
    }


def _irc_for_category(category: str) -> str:
    """Return the default IRC section the treaty article overrides for this category."""
    mapping = {
        "scholarship_fellowship": "§871(a)(1)(B)",  # FDAP withholding on scholarships
        "student_personal_services": "§871(b)",     # ECI taxation of student wages
        "teaching_research": "§871(b)",             # ECI taxation of teacher comp
        "independent_personal_services": "§871(b)",
        "dependent_personal_services": "§871(b)",
        "foreign_source_remittance": "§61",         # default inclusion of income
    }
    return mapping.get(category, "§871")
