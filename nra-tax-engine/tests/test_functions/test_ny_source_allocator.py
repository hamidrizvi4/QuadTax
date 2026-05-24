"""Tests for the NY-source income allocator."""

from src.functions.ny_source_allocator import allocate


class TestNYSourceAllocator:
    def test_100_pct_ny_workdays_full_apportionment(self):
        r = allocate(
            total_w2_wages=30000.0,
            ny_work_days=200,
            total_work_days=200,
            employer_in_ny=True,
        )
        assert r.ny_source_wages == 30000.0
        assert r.ny_source_pct == 1.0
        assert r.non_ny_source_wages == 0.0

    def test_partial_ny_workdays_pro_rata(self):
        r = allocate(
            total_w2_wages=30000.0,
            ny_work_days=100,
            total_work_days=200,
            employer_in_ny=True,
        )
        assert r.ny_source_wages == 15000.0
        assert r.ny_source_pct == 0.5

    def test_employer_outside_ny_yields_zero_ny_source(self):
        r = allocate(
            total_w2_wages=30000.0,
            ny_work_days=0,
            total_work_days=200,
            employer_in_ny=False,
        )
        assert r.ny_source_wages == 0.0
        assert r.non_ny_source_wages == 30000.0

    def test_no_work_day_data_defaults_to_100_pct_when_ny_employer(self):
        r = allocate(
            total_w2_wages=30000.0,
            ny_work_days=0,
            total_work_days=0,
            employer_in_ny=True,
        )
        assert r.ny_source_wages == 30000.0
        assert r.ny_source_pct == 1.0

    def test_1042s_in_ny_institution_full_source(self):
        r = allocate(
            total_w2_wages=0.0,
            ny_work_days=0,
            total_work_days=0,
            total_1042s_gross=22000.0,
            institution_1042s_in_ny=True,
        )
        assert r.ny_source_1042s_gross == 22000.0

    def test_1042s_outside_ny_institution_excluded(self):
        r = allocate(
            total_w2_wages=0.0,
            ny_work_days=0,
            total_work_days=0,
            total_1042s_gross=22000.0,
            institution_1042s_in_ny=False,
        )
        assert r.ny_source_1042s_gross == 0.0
