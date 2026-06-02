"""Post-layer reasonability validators.

Each function inspects ``state`` after a layer completes and appends a
human-readable reason to ``state.requires_human_review`` when something
looks wrong. The engine refuses to advance to assembly while
``requires_human_review`` is non-empty.

These are *reasonability* checks, not strict invariants — they catch the
classes of LLM-extraction error the system is most prone to (decimal
shifts, missing zero, unit confusion) without producing false positives
on legitimate edge cases. A CPA can override the gate at the API by
explicitly acknowledging each reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


# Reasonability bounds. These are intentionally wide — anything outside is
# almost certainly an LLM-extraction error rather than a real filer.
MIN_REASONABLE_WAGES = 0.0
MAX_REASONABLE_WAGES = 10_000_000.0
MAX_REASONABLE_FICA_REFUND = 50_000.0


def _flag(state: "ReturnStateObject", reason: str) -> None:
    if reason not in state.requires_human_review:
        state.requires_human_review.append(reason)


def validate_post_l1(state: "ReturnStateObject") -> List[str]:
    """Sanity-check residency outputs."""
    residency = state.residency
    if residency.spt_days_current_year < 0 or residency.spt_days_current_year > 366:
        _flag(
            state,
            f"L1: SPT day count ({residency.spt_days_current_year}) is outside 0-366.",
        )
    if residency.years_in_exempt_status < 0 or residency.years_in_exempt_status > 30:
        _flag(
            state,
            f"L1: years_in_exempt_status ({residency.years_in_exempt_status}) is implausible.",
        )
    if residency.status == "dual_status":
        _flag(
            state,
            "L1: Dual-status return detected — residency changed mid-year. "
            "QuadTax computes the NRA portion only. A CPA must verify the "
            "resident-alien portion separately (Form 1040 + Form 1040-NR).",
        )
    return state.requires_human_review


def validate_post_l3(state: "ReturnStateObject") -> List[str]:
    """Sanity-check income totals."""
    income = state.income
    if income.total_w2_wages < MIN_REASONABLE_WAGES:
        _flag(state, f"L3: negative W-2 wages ({income.total_w2_wages}) is invalid.")
    if income.total_w2_wages > MAX_REASONABLE_WAGES:
        _flag(
            state,
            f"L3: W-2 wages ({income.total_w2_wages:,.0f}) exceed the "
            f"{MAX_REASONABLE_WAGES:,.0f} reasonability ceiling — likely an OCR error.",
        )
    if income.total_1042s_gross < 0:
        _flag(state, f"L3: negative 1042-S gross ({income.total_1042s_gross}).")

    # Box-3 wages should be >= Box-1 wages in practice (or 0 if the W-2 doesn't
    # report SS wages). Box-2 federal withholding should be <= ~45% of box 1.
    if (
        income.total_w2_wages > 0
        and income.total_w2_withholding > income.total_w2_wages * 0.6
    ):
        _flag(
            state,
            f"L3: federal withholding ${income.total_w2_withholding:,.0f} is > 60% of "
            f"wages ${income.total_w2_wages:,.0f} — verify W-2 Box 2.",
        )
    return state.requires_human_review


def validate_post_l4(state: "ReturnStateObject") -> List[str]:
    """Sanity-check treaty application."""
    treaty = state.treaty
    if not treaty.is_eligible:
        return state.requires_human_review

    # If a treaty article was applied, the country must be present in the
    # seeded database. We can't reach into the evaluator here without coupling,
    # so we rely on the schema invariant that ``country`` is set when
    # ``is_eligible`` is True.
    if not treaty.country:
        _flag(state, "L4: treaty is_eligible=True but no country recorded.")
    if not treaty.article_number:
        _flag(state, "L4: treaty is_eligible=True but no article recorded.")

    # The exempt amount should not exceed gross income.
    total_gross = float(state.income.total_w2_wages) + float(
        state.income.fdap_taxable_total
    )
    if treaty.exempt_amount_applied > total_gross + 1:
        _flag(
            state,
            f"L4: treaty exempt ${treaty.exempt_amount_applied:,.0f} exceeds "
            f"gross income ${total_gross:,.0f}.",
        )
    return state.requires_human_review


def validate_post_l6(state: "ReturnStateObject") -> List[str]:
    """Sanity-check the computed liability."""
    tax = state.tax
    total_income = float(state.income.total_w2_wages) + float(
        state.income.fdap_taxable_total
    )
    if tax.total_tax_liability < 0:
        _flag(state, f"L6: negative tax liability ({tax.total_tax_liability}).")
    if total_income > 0 and tax.total_tax_liability > total_income:
        _flag(
            state,
            f"L6: tax liability ${tax.total_tax_liability:,.0f} exceeds total "
            f"income ${total_income:,.0f}.",
        )
    return state.requires_human_review


def validate_post_l8(state: "ReturnStateObject") -> List[str]:
    """Sanity-check FICA refund amount."""
    fica = state.fica
    total = float(fica.incorrect_ss_withheld) + float(fica.incorrect_medicare_withheld)
    if total > MAX_REASONABLE_FICA_REFUND:
        _flag(
            state,
            f"L8: FICA refund claim ${total:,.0f} exceeds reasonability ceiling.",
        )
    if fica.requires_form_843 and total <= 0:
        _flag(state, "L8: requires_form_843=True but no FICA amount to refund.")
    return state.requires_human_review


VALIDATORS = {
    "L1": validate_post_l1,
    "L3": validate_post_l3,
    "L4": validate_post_l4,
    "L6": validate_post_l6,
    "L8": validate_post_l8,
}


def run_validator(state: "ReturnStateObject", layer: str) -> List[str]:
    """Run the validator registered for ``layer`` if any."""
    fn = VALIDATORS.get(layer)
    if fn is None:
        return state.requires_human_review
    return fn(state)
