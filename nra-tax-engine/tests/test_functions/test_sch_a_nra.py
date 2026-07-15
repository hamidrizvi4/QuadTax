"""Tests for the NRA Schedule A computation."""

from decimal import Decimal

from src.functions.sch_a_nra import (
    SALT_CAP,
    SALT_CAP_MFS,
    SALT_CAP_SINGLE,
    choose_deduction,
    compute_sch_a_nra,
)


class TestSchA:
    def test_under_salt_cap_no_bite(self):
        r = compute_sch_a_nra(
            state_income_tax_withheld=4000,
            local_income_tax_withheld=1500,
            charitable_cash=500,
        )
        assert r.state_local_income_tax == Decimal("5500")
        assert r.salt_cap_bite == Decimal("0")
        assert r.total == Decimal("6000")
        assert r.disallowed_items == []

    def test_above_salt_cap_capped_at_40k_single(self):
        # TY2025 OBBBA-raised cap is $40,000 for single/QSS (was a flat
        # $10,000 pre-2025) — confirmed against the vendored PDF's own
        # printed line 1b text ("smaller of line 1a or $40,000").
        r = compute_sch_a_nra(
            filing_status="single",
            state_income_tax_withheld=30000,
            local_income_tax_withheld=15000,
        )
        assert SALT_CAP == SALT_CAP_SINGLE == Decimal("40000")
        assert r.state_local_income_tax == SALT_CAP_SINGLE
        assert r.salt_cap_bite == Decimal("5000")
        assert r.total == SALT_CAP_SINGLE

    def test_above_salt_cap_capped_at_20k_mfs(self):
        # MFS gets half the single cap ($20,000), per the same printed
        # line 1b text ("... ($20,000 if married filing separately)").
        r = compute_sch_a_nra(
            filing_status="mfs",
            state_income_tax_withheld=15000,
            local_income_tax_withheld=10000,
        )
        assert r.state_local_income_tax == SALT_CAP_MFS
        assert r.salt_cap_bite == Decimal("5000")
        assert r.total == SALT_CAP_MFS

    def test_mfs_cap_does_not_affect_amount_under_20k(self):
        r = compute_sch_a_nra(
            filing_status="mfs",
            state_income_tax_withheld=8000,
            local_income_tax_withheld=5000,
        )
        assert r.state_local_income_tax == Decimal("13000")
        assert r.salt_cap_bite == Decimal("0")

    def test_disallowed_items_flagged_not_added(self):
        r = compute_sch_a_nra(
            state_income_tax_withheld=2000,
            mortgage_interest_attempted=12000,
            property_tax_attempted=4000,
            foreign_income_tax_attempted=300,
            medical_expenses_attempted=800,
        )
        assert r.total == Decimal("2000")
        assert len(r.disallowed_items) == 4
        assert any("Mortgage interest" in item for item in r.disallowed_items)
        assert any("property tax" in item.lower() for item in r.disallowed_items)
        assert any("Foreign income tax" in item for item in r.disallowed_items)
        assert any("Medical expenses" in item for item in r.disallowed_items)

    def test_charitable_and_casualty(self):
        r = compute_sch_a_nra(
            charitable_cash=1000,
            charitable_noncash=300,
            casualty_disaster_loss=2500,
        )
        assert r.total == Decimal("3800")

    def test_to_dict_floats(self):
        r = compute_sch_a_nra(state_income_tax_withheld=500, charitable_cash=200)
        d = r.to_dict_floats()
        assert d["state_local_income_tax"] == 500.0
        assert d["total"] == 700.0
        assert d["disallowed_items"] == []


class TestChooseDeduction:
    def test_itemized_beats_zero_standard(self):
        amt, label = choose_deduction(itemized_total=4500, standard_deduction_available=0)
        assert label == "itemized"
        assert amt == 4500

    def test_india_standard_beats_small_itemized(self):
        amt, label = choose_deduction(
            itemized_total=4500, standard_deduction_available=15000
        )
        assert label == "standard"
        assert amt == 15000

    def test_tie_breaks_to_itemized(self):
        # Tie semantically equivalent — we pick itemized so the user sees the
        # explicit Sch A breakdown.
        amt, label = choose_deduction(
            itemized_total=15000, standard_deduction_available=15000
        )
        assert label == "itemized"
        assert amt == 15000
