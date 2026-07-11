"""Tests for the Form 2210 estimated-tax-penalty evaluator."""

from decimal import Decimal

from src.functions.estimated_tax_penalty import evaluate


class TestSafeHarbor:
    def test_under_1000_underpayment_no_penalty(self):
        r = evaluate(current_year_total_tax=2500, total_withholding=2000)
        assert r.safe_harbor_met is True
        assert "de minimis" in r.safe_harbor_reason

    def test_90_percent_safe_harbor(self):
        # Underpayment of $1,500 is above the $1,000 de minimis but withholding
        # still meets the 90% threshold (15,000 × 0.90 = 13,500 ≤ 13,500).
        r = evaluate(current_year_total_tax=15000, total_withholding=13500)
        assert r.safe_harbor_met is True
        assert "90%" in r.safe_harbor_reason

    def test_100_percent_prior_year_safe_harbor(self):
        r = evaluate(
            current_year_total_tax=12000,
            total_withholding=8000,
            prior_year_total_tax=8000,
            prior_year_agi_over_150k=False,
        )
        assert r.safe_harbor_met is True
        assert "100%" in r.safe_harbor_reason

    def test_110_percent_threshold_high_income(self):
        r = evaluate(
            current_year_total_tax=20000,
            total_withholding=10000,
            prior_year_total_tax=10000,
            prior_year_agi_over_150k=True,
        )
        assert r.safe_harbor_met is False
        assert r.must_attach_form_2210 is True

    def test_estimated_payments_count_toward_safe_harbor(self):
        """estimated_payments must combine with withholding for the 90% test,
        not just withholding alone."""
        r = evaluate(
            current_year_total_tax=15000,
            total_withholding=10000,
            estimated_payments=3500,  # 10000+3500 = 13500 = 90% of 15000
        )
        assert r.safe_harbor_met is True
        assert "90%" in r.safe_harbor_reason


class TestQuarterlyPenaltyCalculation:
    """Regular-method (Form 2210 Part III) real penalty calculation —
    replaces the old worst-case stub (penalty = full underpayment, which
    wildly overstated the real number since it ignored that IRS interest
    only accrues on the outstanding balance for the days it was owed, not
    the whole underpayment for the whole year)."""

    def test_no_safe_harbor_computes_real_interest_based_penalty(self):
        r = evaluate(
            current_year_total_tax=10000,
            total_withholding=2000,
            tax_year=2025,
            annual_rate=0.08,
        )
        assert r.safe_harbor_met is False
        assert r.must_attach_form_2210 is True
        # The old stub would have surfaced the full $8,000 underpayment as
        # the "penalty" — the real interest-based figure must be far
        # smaller (a fraction of a year's interest on partial balances).
        assert Decimal("0") < r.penalty_amount < Decimal("1000")
        assert len(r.periods) == 4

    def test_four_periods_have_correct_due_dates(self):
        r = evaluate(current_year_total_tax=10000, total_withholding=0, tax_year=2025)
        due_dates = [p.due_date.isoformat() for p in r.periods]
        assert due_dates == ["2025-04-15", "2025-06-15", "2025-09-15", "2026-01-15"]

    def test_required_installments_sum_to_required_annual_payment(self):
        """Each period's required installment is 25% of 90% of current tax
        (no prior-year data supplied, so 90% current-year is the only
        threshold available)."""
        r = evaluate(current_year_total_tax=10000, total_withholding=0, tax_year=2025)
        total_required = sum(p.required_installment for p in r.periods)
        assert total_required == Decimal("9000")  # 90% of 10000
        for p in r.periods:
            assert p.required_installment == Decimal("2250")  # 9000 / 4

    def test_periods_empty_when_safe_harbored(self):
        """Sanity: if withholding alone hits the safe harbor, we never reach
        the quarterly math at all."""
        r = evaluate(current_year_total_tax=15000, total_withholding=13500)
        assert r.periods == []

    def test_more_withholding_reduces_penalty(self):
        low_wh = evaluate(current_year_total_tax=10000, total_withholding=1000, tax_year=2025)
        high_wh = evaluate(current_year_total_tax=10000, total_withholding=4000, tax_year=2025)
        assert high_wh.penalty_amount < low_wh.penalty_amount

    def test_estimated_payment_conservatively_credited_to_final_period_only(self):
        """Documented simplification: a lump estimated-payment total (no
        per-payment dates tracked) is assumed paid in the last period —
        worst case for the filer, never understating the penalty. Paying
        the same amount via estimated payments should therefore never
        produce a SMALLER penalty than paying it via evenly-spread
        withholding."""
        via_withholding = evaluate(
            current_year_total_tax=10000, total_withholding=4000, tax_year=2025
        )
        via_late_estimated = evaluate(
            current_year_total_tax=10000,
            total_withholding=0,
            estimated_payments=4000,
            tax_year=2025,
        )
        assert via_late_estimated.penalty_amount >= via_withholding.penalty_amount

    def test_higher_rate_increases_penalty(self):
        low_rate = evaluate(
            current_year_total_tax=10000, total_withholding=2000, tax_year=2025, annual_rate=0.05
        )
        high_rate = evaluate(
            current_year_total_tax=10000, total_withholding=2000, tax_year=2025, annual_rate=0.12
        )
        assert high_rate.penalty_amount > low_rate.penalty_amount

    def test_zero_withholding_full_underpayment_penalty_still_bounded(self):
        """Even a filer with no withholding at all pays interest, not the
        full tax bill, as the 'penalty'."""
        r = evaluate(current_year_total_tax=5000, total_withholding=0, tax_year=2025)
        assert Decimal("0") < r.penalty_amount < Decimal("5000")
