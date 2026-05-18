"""Tests for the Form 2210 safe-harbor evaluator (Phase 3 stub)."""

from decimal import Decimal

from src.functions.estimated_tax_penalty import evaluate


class TestEstimatedTaxPenalty:
    def test_under_1000_underpayment_no_penalty(self):
        r = evaluate(current_year_total_tax=2500, total_withholding_and_estimated=2000)
        assert r.safe_harbor_met is True
        assert "de minimis" in r.safe_harbor_reason

    def test_90_percent_safe_harbor(self):
        # Underpayment of $1,500 is above the $1,000 de minimis but withholding
        # still meets the 90% threshold (15,000 × 0.90 = 13,500 ≤ 13,500).
        r = evaluate(current_year_total_tax=15000, total_withholding_and_estimated=13500)
        assert r.safe_harbor_met is True
        assert "90%" in r.safe_harbor_reason

    def test_100_percent_prior_year_safe_harbor(self):
        r = evaluate(
            current_year_total_tax=12000,
            total_withholding_and_estimated=8000,
            prior_year_total_tax=8000,
            prior_year_agi_over_150k=False,
        )
        assert r.safe_harbor_met is True
        assert "100%" in r.safe_harbor_reason

    def test_110_percent_threshold_high_income(self):
        r = evaluate(
            current_year_total_tax=20000,
            total_withholding_and_estimated=10000,
            prior_year_total_tax=10000,
            prior_year_agi_over_150k=True,
        )
        assert r.safe_harbor_met is False
        assert r.must_attach_form_2210 is True

    def test_no_safe_harbor_surfaces_underpayment(self):
        r = evaluate(current_year_total_tax=10000, total_withholding_and_estimated=2000)
        assert r.safe_harbor_met is False
        assert r.must_attach_form_2210 is True
        assert r.penalty_amount == Decimal("8000")
