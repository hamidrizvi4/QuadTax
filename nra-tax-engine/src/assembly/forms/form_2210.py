"""Form 2210 — Underpayment of Estimated Tax.

Verified against the real 2025 f2210.pdf AcroForm (widget annotations, not
just ``reader.get_fields()``'s aggregated ``/_States_``) field-by-field
against the printed line labels (extracted with a position-aware
``visitor_text`` callback, since the three-page, multi-column layout
interleaves badly under plain linear text extraction). Findings:

  * Page 1 / Part I, lines 1-9 (``f1_3``..``f1_11``) and the "Next: Is line 9
    more than line 6?" Yes/No checkbox pair (``c1_1[0]``=No, ``c1_1[1]``=Yes)
    were previously almost entirely unmapped even though
    ``src/functions/estimated_tax_penalty.py`` already computes lines 4, 5,
    8, and 9 unconditionally (its own docstring says so) — this was data
    sitting in state and simply never reaching the PDF. Now mapped.
  * Line 6 ("Withholding taxes. **Don't** include estimated tax payments")
    and Line 7 ("Subtract line 6 from line 4") were populated from
    ``state.tax.total_withholding_credits`` / ``state.tax.refund_or_owed``,
    both of which fold ``federal_estimated_payments`` in (see
    ``src/agents/l7_credits.py`` and
    ``src/functions/withholding_reconciler.py``'s ``federal_total``
    property). That silently overstated Line 6 (and understated Line 7) by
    the taxpayer's estimated-payment total whenever any estimated payments
    were made — a real tax-correctness bug, not just a missing line. Fixed
    to subtract ``federal_estimated_payments`` back out, matching the exact
    withholding-only figure ``src/orchestrator/engine.py`` already passes as
    ``total_withholding`` into ``estimated_tax_penalty.evaluate()``.
  * Page 2's Section A worksheet (lines 10-18, columns (a)-(d),
    ``SectionATable[0].Line10[0]``..``Line18[0]``, four widgets each) is
    computed by ``estimated_tax_penalty._section_a_worksheet()`` but was
    never mapped to the PDF at all. Now mapped (blank when no safe harbor
    was met — i.e. no computation was needed — matching the real form's own
    "stop here" instruction on line 11).
  * Line 19 ("Penalty") on page 2 (``f2_37``) was already correctly wired
    (previously keyed ``line_17_total_penalty``, which named the wrong line
    number — the field is really line 19; renamed to ``line_19_total_penalty``
    for clarity, no functional change).
  * Part II, "Reasons for Filing" boxes A-E (``c1_2``..``c1_6``) require a
    waiver request, the annualized-income installment method, an
    actual-per-paycheck-withholding-date election, or a joint/separate
    filing-status change between tax years — none of which this engine's
    intake collects. Left unmapped/blank rather than fabricated (see the
    comment above ``_UNMAPPED`` below).
  * Page 3 (Schedule AI — Annualized Income Installment Method, Parts I and
    II) requires income/deduction figures broken out by calendar-quarter
    period, which this engine does not collect (it only tracks annual
    totals). Left entirely unmapped/blank for the same reason — Schedule AI
    is only required when box C (annualized income method) is checked,
    which per the above is never checked here anyway.

The per-period breakdown from the *interest* calculation (four required
installments, cumulative payments credited, days-outstanding interest —
distinct bookkeeping from Section A's column-to-column carryforward, see
``estimated_tax_penalty.py``'s module docstring) is exposed via the
underscore-prefixed ``_periods`` key for the narrative/API layer only; it
has no corresponding fillable field on the real form (Section B's worksheet
lives only in the IRS instructions, not in the AcroForm).
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


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    penalty = getattr(state, "estimated_tax_penalty", None) or {}

    # Line 6 must exclude estimated tax payments per the form's own
    # instruction ("Withholding taxes. Don't include estimated tax
    # payments.") -- total_withholding_credits folds estimated payments in
    # (see withholding_reconciler.WithholdingReport.federal_total), so back
    # them back out here. This is exactly the "total_withholding" figure
    # src/orchestrator/engine.py already passes into
    # estimated_tax_penalty.evaluate(), kept in sync deliberately.
    wh_report = state.withholding_report or {}
    estimated_paid = float(wh_report.get("federal_estimated_payments", 0.0))
    line_6_withholding = max(0.0, float(state.tax.total_withholding_credits) - estimated_paid)

    line_4_current_year_tax = float(penalty.get("line_4_current_year_tax", 0.0))
    # Line 7 = Line 4 minus Line 6 (both withholding-only, no estimated
    # payments folded in -- see the module docstring above for why this
    # differs from the old `refund_or_owed`-derived value). Floored at zero:
    # line 7 only feeds the "is it less than $1,000?" screening question at
    # the top of page 1, so a negative value and zero both mean the same
    # thing for that test, and every other money line in this codebase
    # already floors the same way (see e.g. form_1040nr.py's line_37_owed).
    line_7_value = max(0.0, line_4_current_year_tax - line_6_withholding)

    line_9_required_annual_payment = float(penalty.get("line_9_required_annual_payment", 0.0))
    # "Next: Is line 9 more than line 6?" -- the Yes/No checkbox pair right
    # below Part I, line 9 on page 1. c1_1[0] and c1_1[1] are two distinct
    # single-export-state AcroForm fields (not kids of one radio group), so
    # a bare Python bool resolves correctly via each field's own /_States_
    # fallback -- confirmed by dumping the raw widget annotations rather
    # than trusting reader.get_fields() alone.
    line_9_gt_line_6 = line_9_required_annual_payment > line_6_withholding

    field_map = {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "tin": ident.primary_tin,
        # Line 1 - tax after credits. This engine doesn't separately track
        # "other taxes" (line 2) or "other payments/refundable credits"
        # (line 3) apart from the combined total_tax_liability figure, so
        # line 1 carries the whole amount and lines 2/3 are left blank
        # below -- line 1 + 0 + 0 still correctly reproduces line 4.
        "line_1_tax_after_credits": _fmt_money(state.tax.total_tax_liability),
        # Line 2 ("other taxes") and line 3 ("other payments and refundable
        # credits") have no distinct backing data in ReturnStateObject --
        # see the line 1 comment above. Intentionally left unmapped/blank
        # rather than fabricated.
        "line_4_current_year_tax": _fmt_money(line_4_current_year_tax),
        "line_5_ninety_pct_current_year": _fmt_money(
            penalty.get("line_5_ninety_pct_current_year", 0.0)
        ),
        "line_6_withholding": _fmt_money(line_6_withholding),
        "line_7_line4_minus_line6": _fmt_money(line_7_value),
        # Line 8 (maximum required annual payment based on prior year's
        # tax) is None whenever no prior-year tax figure was supplied --
        # this engine currently collects none (see
        # estimated_tax_penalty.py's EstimatedTaxPenaltyResult.line_8_prior_year_max
        # docstring) -- matching the real form's own instruction that line 8
        # is only completed when you have a prior-year amount to compare
        # against.
        "line_8_prior_year_max": _fmt_money(penalty.get("line_8_prior_year_max")),
        "line_9_required_annual_payment": _fmt_money(line_9_required_annual_payment),
        "checkbox_line9_more_than_line6_no": not line_9_gt_line_6,
        "checkbox_line9_more_than_line6_yes": line_9_gt_line_6,
        "line_19_total_penalty": _fmt_money(penalty.get("penalty_amount", 0.0)),
        "_safe_harbor_met": penalty.get("safe_harbor_met", True),
        "_safe_harbor_reason": penalty.get("safe_harbor_reason", "Default safe harbor."),
        "_periods": penalty.get("periods", []),
    }

    # Section A worksheet (page 2, lines 10-18, columns a-d) -- only
    # meaningful (and only computed by estimated_tax_penalty.py) when no
    # safe harbor was met; when it was, the real form's own line 11
    # instruction says to stop, so leaving these blank matches what a human
    # filer would actually do, not a gap in this mapping.
    section_a = penalty.get("section_a") or []
    columns = "abcd"
    for col_idx, letter in enumerate(columns):
        column = section_a[col_idx] if col_idx < len(section_a) else {}
        for line_no in range(10, 19):
            value = column.get(f"line_{line_no}")
            field_map[f"section_a_line{line_no}_{letter}"] = _fmt_money(value)

    return field_map
