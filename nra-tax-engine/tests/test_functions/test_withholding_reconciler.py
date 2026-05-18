"""Tests for the withholding reconciler."""

from decimal import Decimal

from src.functions.withholding_reconciler import (
    Form1042SEntry,
    Form1099Entry,
    W2Entry,
    reconcile,
)


class TestReconcile:
    def test_empty_inputs_zero_totals(self):
        report = reconcile()
        assert report.federal_total == Decimal("0")
        assert report.ss_withheld_w2 == Decimal("0")

    def test_two_w2s_summed(self):
        report = reconcile(
            w2s=[
                W2Entry(
                    box_2_fed_withholding=1500.0,
                    box_4_ss_withheld=500.0,
                    box_6_medicare_withheld=120.0,
                ),
                W2Entry(
                    box_2_fed_withholding=2000.0,
                    box_4_ss_withheld=700.0,
                    box_6_medicare_withheld=170.0,
                ),
            ]
        )
        assert report.federal_w2 == Decimal("3500")
        assert report.ss_withheld_w2 == Decimal("1200")
        assert report.medicare_withheld_w2 == Decimal("290")
        assert "W-2" in report.sources_seen

    def test_chapter_3_vs_4_split(self):
        report = reconcile(
            f1042s=[
                Form1042SEntry(box_7a_fed_withheld=500.0, chapter_indicator=3),
                Form1042SEntry(box_7a_fed_withheld=200.0, chapter_indicator=4),
            ]
        )
        assert report.federal_1042s_ch3 == Decimal("500")
        assert report.federal_1042s_ch4 == Decimal("200")
        assert report.federal_total == Decimal("700")

    def test_1099_and_estimated_payments(self):
        report = reconcile(
            f1099s=[
                Form1099Entry(form_kind="INT", fed_withholding=80.0),
                Form1099Entry(form_kind="DIV", fed_withholding=120.0),
            ],
            estimated_payments=[1000.0, 1000.0, 500.0],
        )
        assert report.federal_1099 == Decimal("200")
        assert report.federal_estimated_payments == Decimal("2500")
        assert report.federal_total == Decimal("2700")

    def test_ny_and_nyc_withholding_captured(self):
        report = reconcile(
            w2s=[
                W2Entry(
                    box_17_state_income_tax=800.0,
                    box_19_local_income_tax=300.0,
                    box_20_locality_name="NYC",
                )
            ]
        )
        assert report.state_income_tax_w2 == Decimal("800")
        assert report.local_income_tax_w2 == Decimal("300")

    def test_to_dict_floats(self):
        report = reconcile(
            w2s=[W2Entry(box_2_fed_withholding=1234.56)],
        )
        d = report.to_dict_floats()
        assert d["federal_w2"] == 1234.56
        assert d["federal_total"] == 1234.56
