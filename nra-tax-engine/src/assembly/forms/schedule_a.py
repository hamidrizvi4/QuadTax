"""Schedule A (1040-NR) — NRA itemized deductions.

Reads the pre-computed totals from :attr:`ReturnStateObject.sch_a` (populated
by :func:`src.functions.sch_a_nra.compute_sch_a_nra`).

Field mapping verified against the real vendored TY2025 AcroForm PDF
(``assets/templates/2025/f1040nra.pdf``) by walking every widget
annotation's ``/Parent`` chain for its fully-qualified field name and
cross-referencing against the printed line text via a position-sorted
(x, y) text extraction, then visually re-confirmed by rendering the page
to an image. Findings that changed this module from an earlier version:

    * f1_1[0] / f1_2[0] (the "Name shown on Form 1040-NR" / "Your
      identifying number" header repeated at the top of every attached
      schedule — the same convention schedule_oi.py and schedule_nec.py
      already follow for their own copies of this AcroForm hierarchy)
      were completely unmapped. Fixed below.

    * Lines 1a and 1b are TWO DIFFERENT NUMBERS, not one value duplicated:
      line 1a (f1_3[0]) is the RAW, pre-cap state+local income tax paid;
      line 1b (f1_4[0]) is "the smaller of line 1a or $40,000 ($20,000 if
      MFS)" — i.e., the post-SALT-cap amount that actually flows into the
      line 8 total (per the form's own line 8 instructions: "Add the
      amounts in the far right column for lines 1b through 7"). A prior
      version of this module (a) wrote the ALREADY-CAPPED amount onto line
      1a — silently understating line 1a whenever the cap actually bit —
      and (b) wrote a free-text warning sentence (e.g. "SALT cap reduced
      total by $3,000") into line 1b, which is a numeric AcroForm text
      field expected to hold the capped dollar figure, not prose. Both are
      fixed below: line 1a now reports the true raw pre-cap total
      (reconstructed as capped + bite, which recovers the exact raw value
      compute_sch_a_nra started from — see inline comment), and line 1b
      reports the actual capped number. The human-readable SALT-cap
      explanation is preserved as an underscore-prefixed audit-only key
      (``_salt_cap_bite_note``) instead of being crammed into a PDF money
      field.

    * Line 7's free-text "type" description box (Line7Entry[0].f1_10[0],
      the multi-line dashed area under "Other—from list in instructions.
      List type and amount:") has no backing state field — SchAResult's
      ``other_itemized`` is a bare dollar amount with no category/label
      captured anywhere upstream. Left unmapped rather than fabricating a
      description; only the dollar amount (line 7's own right-column
      total, f1_11[0]) is filled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def _fmt_money(value) -> str:
    if value in (None, ""):
        return ""
    try:
        rounded = round(float(value))
    except (TypeError, ValueError):
        return ""
    return "" if rounded == 0 else str(rounded)


def _full_name(ident) -> str:
    parts = [ident.first_name, ident.middle_initial, ident.last_name, ident.suffix]
    return " ".join(p for p in parts if p)


def compute_field_map(state: "ReturnStateObject") -> dict:
    sch_a = state.sch_a or {}
    ident = state.identity

    capped_state_local = float(sch_a.get("state_local_income_tax", 0.0) or 0.0)
    salt_cap_bite = float(sch_a.get("salt_cap_bite", 0.0) or 0.0)
    # compute_sch_a_nra sets state_local_income_tax = min(raw, cap) and
    # salt_cap_bite = max(raw - cap, 0) — so capped + bite reconstructs the
    # exact pre-cap raw total in both the capped and uncapped branches,
    # without needing separate raw-input fields threaded through state.sch_a.
    raw_state_local = capped_state_local + salt_cap_bite

    charitable_cash = float(sch_a.get("charitable_cash", 0.0) or 0.0)
    charitable_noncash = float(sch_a.get("charitable_noncash", 0.0) or 0.0)
    # No intake/state field for a prior-year Schedule A charitable carryover
    # exists anywhere in this engine (ReturnStateObject.sch_a has no such
    # key) — genuinely un-fixable from here, left at 0 rather than guessed.
    carryover = 0.0

    return {
        # Header — every attached schedule must repeat the filer's name and
        # identifying number (see module docstring).
        "header_name": _full_name(ident),
        "header_identifying_number": ident.primary_tin,
        # Line 1a: raw, pre-SALT-cap state+local income tax paid.
        "line_1a_state_local_income_tax": _fmt_money(raw_state_local),
        # Line 1b: smaller of line 1a or the SALT cap — the figure that
        # actually flows into the line 8 total.
        "line_1b_salt_cap_amount": _fmt_money(capped_state_local),
        "line_2_cash_gifts": _fmt_money(charitable_cash),
        "line_3_noncash_gifts": _fmt_money(charitable_noncash),
        "line_4_carryover": _fmt_money(carryover),
        "line_5_total_gifts": _fmt_money(charitable_cash + charitable_noncash + carryover),
        "line_6_casualty_disaster": _fmt_money(sch_a.get("casualty_disaster_loss", 0.0)),
        "line_7_other_itemized": _fmt_money(sch_a.get("other_itemized", 0.0)),
        "line_8_total_itemized": _fmt_money(sch_a.get("total", 0.0)),
        # Audit/UI-only — never written to the PDF (underscore-prefixed keys
        # are filtered out by FormPopulator._inject_pdf_data).
        "_disallowed_items_warnings": sch_a.get("disallowed_items", []),
        "_salt_cap_bite_note": (
            f"SALT cap reduced the deductible amount by ${salt_cap_bite:,.0f}"
            if salt_cap_bite > 0
            else ""
        ),
    }
