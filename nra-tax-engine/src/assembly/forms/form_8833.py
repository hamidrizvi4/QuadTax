"""Form 8833 — Treaty-Based Return Position Disclosure (IRC §6114 / §7701(b)).

One Form 8833 is generated per qualifying treaty benefit. The populator
returns a list of per-benefit field maps in ``rows``; the PDF writer
clones the template N times and fills each clone from the corresponding
row.

Real AcroForm field layout (dumped from assets/templates/2025/f8833.pdf,
Rev. December 2022, single-page form; verified against
``_field_maps/f8833_p1.png``):

    f1_1                Name
    f1_2                U.S. taxpayer identifying number
    f1_3                Reference ID number, if any
    f1_4                Address in country of residence
    f1_5                Address in the United States
    c1_1 (states /1,/Off)   "disclosing ... as required by section 6114" box
    c1_2 (states /1,/Off)   dual-resident taxpayer / Reg 301.7701(b)-7 box
    c1_3 (states /1,/Off)   "taxpayer is a U.S. citizen or resident ... " box
    Lines1-2_ReadOrder.f1_6   Line 1a — treaty country
    Lines1-2_ReadOrder.f1_7   Line 1b — article(s)
    f1_8                Line 2 — IRC provision(s) overruled/modified
    f1_9                Line 3 — payor name/ID/US address (FDAP items only)
    f1_10               Line 4 — limitation-on-benefits provision(s)
    c1_4[0] (states /1,/Off)  Line 5 "Yes" box (Reg 301.6114-1(b) reporting)
    c1_4[1] (states /2,/Off)  Line 5 "No" box
    f1_11               Line 5 — specific subsection(s), if "Yes"
    f1_12 .. f1_36      Line 6 explanation — 25 *single-line* text fields
                        (f1_12 is a narrow trailing slot on the same row as
                        the printed instructions; f1_13..f1_36 are 24
                        full-width ruled lines below it). None of these are
                        multiline fields, so long explanations must be
                        word-wrapped across them by the populator rather
                        than dumped into one field.

Fields left unmapped (no backing intake/state data — see comments below):
    * f1_3  — Reference ID number (not applicable to individual filers;
      no state field represents this concept).
    * f1_9  — Line 3 payor name/ID/US address. ``state.income.employer_name``
      / ``employer_ein`` give a *name* and *EIN* but the form explicitly asks
      for the payor's *US address*, which nothing in ``ReturnStateObject``
      captures (no per-1042-S/W-2 payor address is collected). For
      scholarship/fellowship benefits the payor is often the institution,
      not "the employer," so even the name is not reliably right. Left
      blank rather than fabricating an address or guessing the payor.
    * f1_10 — Line 4 limitation-on-benefits provision(s). No LOB-article
      data is captured anywhere in ``TreatyState``/``applied_benefits``.
    * f1_11 — Line 5 "if Yes" specific Reg 301.6114-1(b) subsection cite.
      No per-article mapping to the regulation's enumerated subsections
      exists in state; citing the wrong subsection would be worse than
      leaving it blank.
    * c1_2  — dual-resident-taxpayer / Reg 301.7701(b)-7 box. This engine's
      filer population is NRAs claiming ordinary treaty benefits under
      §6114, not the §7701(b) long-term-resident dual-resident election
      (a distinct, rare fact pattern this engine does not model). Always
      left unchecked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject

# Per-line character budgets for word-wrapping the Line 6 explanation across
# the 25 single-line text fields (f1_12..f1_36). f1_12 sits in a narrower
# trailing slot (~252pt wide) on the same row as the printed instructions;
# f1_13..f1_36 are full-width ruled lines (~511pt wide). At the form's ~10pt
# Helvetica these translate to roughly 42 and 90 characters respectively;
# kept a little conservative so nothing overflows its box.
_LINE6_FIRST_LINE_WIDTH = 42
_LINE6_FULL_LINE_WIDTH = 90
_LINE6_MAX_LINES = 25  # f1_12 through f1_36 inclusive


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    rows: List[dict] = []

    foreign_address = _format_address(
        ident.foreign_address_line1,
        ident.foreign_address_line2,
        ident.foreign_city,
        ident.foreign_state_province,
        ident.foreign_postal_code,
        ident.foreign_country,
    )
    us_address = _format_address(
        ident.us_address_line1,
        ident.us_address_line2,
        ident.us_city,
        ident.us_state,
        ident.us_zip,
        "",
    )

    # This engine only files Form 8833 for NRAs disclosing an ordinary
    # treaty-based return position under IRC §6114 (never the §7701(b)
    # dual-resident/long-term-resident election), so the top checkbox pair
    # is fixed: the §6114 box is always checked, the dual-resident box
    # never is.
    check_6114 = "/1"
    check_dual_resident = "/Off"
    # The "taxpayer is a U.S. citizen or resident ... " box is the inverse
    # disclosure — it only applies when the filer is NOT the nonresident
    # alien this engine otherwise assumes. Driven by the actual residency
    # determination rather than hardcoded, so a resident-alien filer who
    # still needs an 8833 (e.g. a saving-clause-surviving benefit) gets it
    # checked correctly.
    check_us_citizen_or_resident = (
        "/1" if state.residency.status == "resident_alien" else "/Off"
    )

    for benefit in state.treaty.applied_benefits:
        if not benefit.get("requires_form_8833"):
            continue

        explanation_text = _build_line6_text(benefit)
        explanation_lines = _wrap_to_widths(
            explanation_text,
            [_LINE6_FIRST_LINE_WIDTH, _LINE6_FULL_LINE_WIDTH],
        )[:_LINE6_MAX_LINES]

        # Line 5: "Is the taxpayer disclosing a treaty-based return position
        # for which reporting is specifically required pursuant to
        # Regulations section 301.6114-1(b)?" This populator only ever
        # emits a row when ``benefit["requires_form_8833"]`` is True, and
        # that flag is computed (see treaty_evaluator._form_8833_required)
        # by applying the §6114/Reg 301.6114-1 disclosure rule net of the
        # Notice 2010-21 routine-position exception. A benefit that reaches
        # this loop has therefore already been determined to be a
        # reportable position under 301.6114-1(b) — if it weren't, no 8833
        # would be generated for it at all. So Line 5 is always "Yes" here.
        rows.append(
            {
                "box_1a_name": f"{ident.first_name} {ident.last_name}".strip(),
                "box_1b_tin": ident.primary_tin,
                "box_1d_address_foreign": foreign_address,
                "box_1e_address_us": us_address,
                "box_check_6114": check_6114,
                "box_check_dual_resident": check_dual_resident,
                "box_check_us_citizen_or_resident": check_us_citizen_or_resident,
                "box_2_treaty_country": benefit.get("country_name", ""),
                "box_3_treaty_article": benefit.get("article_id", ""),
                "box_4_irc_provision_overridden": _irc_for_category(benefit.get("category", "")),
                "box_5_explanation": explanation_text,
                "box_5_explanation_rows": [{"text": line} for line in explanation_lines],
                "box_5_reg_6114_1b_yes": "/1",
                "box_5_reg_6114_1b_no": "/Off",
                # Kept for audit/back-compat consumers (e.g. review UI, tests) —
                # not written directly to the PDF; the dollar amount is folded
                # into the Line 6 narrative text instead (see
                # treaty_evaluator._build_explanation), matching the form's
                # actual instructions ("list the nature and amount ... for
                # which the treaty benefit is claimed" as part of Line 6,
                # not a standalone numeric line).
                "box_6_amount_exempted": float(benefit.get("exempt_amount", 0.0)),
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


def _build_line6_text(benefit: dict) -> str:
    """Compose the full Line 6 narrative for one applied treaty benefit.

    ``benefit["explanation"]`` (built in ``treaty_evaluator._build_explanation``)
    already states the article, category, and dollar amount/cap — exactly
    what Line 6's instructions ask for ("brief summary of the facts ...
    Also, list the nature and amount ... for which the treaty benefit is
    claimed"). Line 6 is the *only* place on the real form for the dollar
    amount (there is no separate "amount exempted" line), so this defends
    against an ``explanation`` string that, for whatever reason, doesn't
    already spell the figure out — appending it explicitly rather than
    trusting upstream text to always include it. A saving-clause note is
    appended the same way, only when the *filer's* circumstances actually
    invoke the exception (``applies_after_saving_clause`` is filer-specific
    — true only once the filer has become a resident alien).
    """
    text = (benefit.get("explanation") or "").strip()

    exempt_amount = float(benefit.get("exempt_amount", 0.0) or 0.0)
    if exempt_amount:
        amount_str = f"${exempt_amount:,.0f}"
        if amount_str not in text:
            text = f"{text} The treaty benefit claimed is {amount_str}.".strip()

    if benefit.get("applies_after_saving_clause") and "saving" not in text.lower():
        addendum = (
            "This position applies notwithstanding the treaty's saving "
            "clause; see the applicable protocol saving-clause exception "
            "for this article."
        )
        text = f"{text} {addendum}".strip()
    return text


def _format_address(
    line1: str, line2: str, city: str, state_or_province: str, postal_code: str, country: str
) -> str:
    """Compose a single-line mailing address from discrete intake fields.

    Any missing component is simply omitted (no dangling commas/spaces).
    """
    street = " ".join(p for p in (line1, line2) if p)
    csz = ", ".join(p for p in (city, state_or_province) if p)
    csz = " ".join(p for p in (csz, postal_code) if p)
    return ", ".join(p for p in (street, csz, country) if p)


def _wrap_to_widths(text: str, widths: List[int]) -> List[str]:
    """Greedy word-wrap ``text`` using a per-line character budget.

    ``widths[i]`` bounds line ``i``; once ``widths`` is exhausted, the last
    entry is reused for every subsequent line. Used to lay ``text`` out
    across a run of same-purpose-but-different-width single-line PDF text
    fields (Form 8833's Line 6 explanation: a narrow first slot followed by
    24 full-width ruled lines).
    """
    text = " ".join(text.split())  # normalize whitespace
    if not text:
        return []

    words = text.split(" ")
    lines: List[str] = []
    current: List[str] = []

    def width_for(line_index: int) -> int:
        return widths[line_index] if line_index < len(widths) else widths[-1]

    for word in words:
        budget = width_for(len(lines))
        candidate = " ".join(current + [word]) if current else word
        if current and len(candidate) > budget:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines
