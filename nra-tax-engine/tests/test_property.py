"""Property-based invariants — Phase 8.

Hypothesis generates random income, withholding, and treaty configurations
and asserts the engine's accounting identity:

    refund_or_owed = total_tax_liability − total_withholding_credits

plus a few related invariants (bracket monotonicity, treaty exempt ≤ gross,
non-negative tax). Strategies are kept narrow (US dollars, finite ranges)
so the suite finishes in well under a minute.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from src.functions.tax_math import TaxCalculator
from src.functions.treaty_evaluator import TreatyEvaluator


money = st.floats(min_value=0.0, max_value=500_000.0, allow_nan=False, allow_infinity=False)
small_money = st.floats(min_value=0.0, max_value=50_000.0, allow_nan=False, allow_infinity=False)
fdap_rate = st.sampled_from([0.0, 0.10, 0.14, 0.15, 0.30])


@settings(max_examples=80, deadline=None)
@given(eci=money, fdap=money, rate=fdap_rate)
def test_total_equals_sum_of_parts(eci, fdap, rate):
    """total_tax_liability is exactly the sum of ECI + FDAP tax components."""
    calc = TaxCalculator(tax_year=2025, filing_status="single")
    r = calc.calculate_tax_liability(eci, fdap, rate)
    assert r["total_tax_liability"] == r["eci_tax_liability"] + r["fdap_tax_liability"]


@settings(max_examples=80, deadline=None)
@given(eci=money, fdap=money, rate=fdap_rate)
def test_tax_is_non_negative(eci, fdap, rate):
    """No income/rate combo produces a negative tax."""
    calc = TaxCalculator(tax_year=2025, filing_status="single")
    r = calc.calculate_tax_liability(eci, fdap, rate)
    assert r["eci_tax_liability"] >= 0
    assert r["fdap_tax_liability"] >= 0
    assert r["total_tax_liability"] >= 0


@settings(max_examples=60, deadline=None)
@given(
    eci_low=st.floats(min_value=0.0, max_value=200_000.0, allow_nan=False),
    delta=st.floats(min_value=1.0, max_value=10_000.0, allow_nan=False),
)
def test_eci_brackets_are_monotone(eci_low, delta):
    """Tax on a larger ECI ≥ tax on a smaller ECI (graduated brackets are monotone)."""
    calc = TaxCalculator(tax_year=2025, filing_status="single")
    low = calc.calculate_tax_liability(eci_low, 0.0, 0.30)["eci_tax_liability"]
    high = calc.calculate_tax_liability(eci_low + delta, 0.0, 0.30)["eci_tax_liability"]
    assert high >= low


@settings(max_examples=60, deadline=None)
@given(eci=money)
def test_marginal_bracket_below_max_rate(eci):
    """Effective rate on any ECI ≤ 37% top marginal (TY2025 single)."""
    calc = TaxCalculator(tax_year=2025, filing_status="single")
    r = calc.calculate_tax_liability(eci, 0.0, 0.0)
    if eci > 0:
        effective = r["eci_tax_liability"] / eci
        assert effective <= 0.37 + 1e-9


@settings(max_examples=50, deadline=None)
@given(rate=fdap_rate, fdap=money)
def test_fdap_tax_is_exact_rate(rate, fdap):
    """FDAP tax exactly equals rate × amount (rounded)."""
    calc = TaxCalculator(tax_year=2025, filing_status="single")
    r = calc.calculate_tax_liability(0.0, fdap, rate)
    assert r["fdap_tax_liability"] == pytest.approx(round(rate * fdap), abs=0.5)


# ---------------------------------------------------------------------------
# Treaty evaluator invariants
# ---------------------------------------------------------------------------


_evaluator = TreatyEvaluator(tax_year=2025)
_countries = list(_evaluator.countries.keys())


@settings(max_examples=80, deadline=None)
@given(
    country=st.sampled_from(_countries),
    years=st.integers(min_value=1, max_value=10),
    gross=small_money,
)
def test_treaty_exempt_never_exceeds_gross(country, years, gross):
    """No matter the country/year/income, exempt_amount ≤ gross."""
    benefits = _evaluator.evaluate(
        country=country,
        visa_type="F-1",
        residency_status="nonresident_alien",
        years_since_arrival=years,
        gross_by_category={"student_personal_services": gross},
        is_us_source_by_category={"student_personal_services": True},
    )
    for b in benefits:
        assert b.exempt_amount <= gross + 0.01


@settings(max_examples=80, deadline=None)
@given(
    country=st.sampled_from(_countries),
    years=st.integers(min_value=1, max_value=10),
    gross=small_money,
)
def test_treaty_exempt_is_non_negative(country, years, gross):
    benefits = _evaluator.evaluate(
        country=country,
        visa_type="F-1",
        residency_status="nonresident_alien",
        years_since_arrival=years,
        gross_by_category={"student_personal_services": gross},
        is_us_source_by_category={"student_personal_services": True},
    )
    for b in benefits:
        assert b.exempt_amount >= 0


# ---------------------------------------------------------------------------
# Accounting identity at the orchestrator level (no LLM — pre-populated state)
# ---------------------------------------------------------------------------


@settings(max_examples=40, deadline=None)
@given(liability=money, credits_amt=money)
def test_refund_or_owed_identity(liability, credits_amt):
    """state.tax.refund_or_owed = total_tax_liability − total_withholding_credits."""
    from src.agents.l7_credits import CreditsAgent
    from src.orchestrator.state import ReturnStateObject

    state = ReturnStateObject(tax_year=2025)
    state.tax.total_tax_liability = liability
    state.income.total_w2_withholding = credits_amt
    state.income.total_1042s_withholding = 0.0

    CreditsAgent().process_credits(state)
    expected = round(liability - credits_amt, 6)
    actual = round(state.tax.refund_or_owed, 6)
    assert actual == pytest.approx(expected, abs=0.5)
