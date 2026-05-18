"""Tests for the year-keyed tax-data loader."""

import pytest

from src.database.tax_year import (
    NRA_ALLOWED_FILING_STATUSES,
    load_year,
)


class TestLoadYear2025:
    def setup_method(self):
        self.year = load_year(2025)

    def test_year_field_matches(self):
        assert self.year.tax_year == 2025

    def test_single_brackets_top_threshold(self):
        single = self.year.brackets["single"]
        # 2025 single 37% bracket starts at $626,350 (Rev. Proc. 2024-40).
        top = single[-1]
        assert top.rate == 0.37
        assert single[-2].up_to == 626350

    def test_single_brackets_first_two_rows(self):
        single = self.year.brackets["single"]
        assert single[0].rate == 0.10
        assert single[0].up_to == 11925
        assert single[1].rate == 0.12
        assert single[1].up_to == 48475

    def test_mfs_brackets_diverge_at_35_pct(self):
        """In TY2025, MFS 37% kicks in at $375,800; single's at $626,350."""
        mfs = self.year.brackets["mfs"]
        assert mfs[-1].rate == 0.37
        assert mfs[-2].up_to == 375800

    def test_qss_brackets_present(self):
        qss = self.year.brackets["qss"]
        assert qss[0].up_to == 23850

    def test_standard_deduction_nra_default_zero(self):
        sd = self.year.standard_deduction
        assert sd.for_status("single", india_treaty=False) == 0.0

    def test_standard_deduction_india_single(self):
        sd = self.year.standard_deduction
        assert sd.for_status("single", india_treaty=True) == 15000.0

    def test_fica_wage_base_and_rates(self):
        ss = self.year.fica.social_security
        assert ss["wage_base"] == 176100
        assert ss["employee_rate"] == pytest.approx(0.062)
        med = self.year.fica.medicare
        assert med["employee_rate"] == pytest.approx(0.0145)

    def test_amt_single_exemption(self):
        assert self.year.amt.exemption["single"] == 88100

    def test_sch_nec_default_rate(self):
        assert self.year.sch_nec.default_rate == 0.30
        assert self.year.sch_nec.category_rates["scholarship_fellowship_fjmq_visa"] == 0.14

    def test_ny_block_present(self):
        assert self.year.ny is not None
        assert self.year.ny["treaty_conformity"]["honors_federal_treaties"] is False

    def test_filing_status_constants(self):
        assert "single" in NRA_ALLOWED_FILING_STATUSES
        assert "mfs" in NRA_ALLOWED_FILING_STATUSES
        assert "qss" in NRA_ALLOWED_FILING_STATUSES
        assert "mfj" not in NRA_ALLOWED_FILING_STATUSES
        assert "hoh" not in NRA_ALLOWED_FILING_STATUSES


class TestLoadYearMissing:
    def test_unknown_year_raises(self):
        with pytest.raises(FileNotFoundError):
            load_year(1999)
