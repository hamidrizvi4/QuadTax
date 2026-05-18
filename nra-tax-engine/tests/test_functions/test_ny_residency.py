"""Tests for the NY residency classifier (Knight case + statutory residency)."""

from src.functions.ny_residency import evaluate


class TestNYResidency:
    def test_f1_in_dorm_year_round_is_nonresident(self):
        """F-1 student in NYU dorm year-round → NY nonresident (Knight case)."""
        r = evaluate(
            days_in_ny=330,
            has_permanent_abode_in_ny=True,
            abode_months_in_year=12,
            is_student_dorm=True,
            domiciled_in_ny=False,
        )
        assert r.status == "nonresident"
        assert "dormitory" in r.reason.lower() or "knight" in r.reason.lower()

    def test_f1_brooklyn_year_round_apartment_is_statutory_resident(self):
        """F-1 with a Brooklyn apartment for 12 months and 200 days in NY → statutory resident."""
        r = evaluate(
            days_in_ny=200,
            has_permanent_abode_in_ny=True,
            abode_months_in_year=12,
            is_student_dorm=False,
            domiciled_in_ny=False,
            nyc_address=True,
        )
        assert r.status == "resident"
        assert r.nyc_resident is True

    def test_statutory_residency_fails_below_184_days(self):
        """Even with a year-round apartment, ≤ 183 days → nonresident."""
        r = evaluate(
            days_in_ny=180,
            has_permanent_abode_in_ny=True,
            abode_months_in_year=12,
            is_student_dorm=False,
            domiciled_in_ny=False,
        )
        assert r.status == "nonresident"
        assert "183" in r.reason

    def test_statutory_residency_fails_below_11_months_abode(self):
        """Less than 11 months of abode → nonresident under the duration prong."""
        r = evaluate(
            days_in_ny=300,
            has_permanent_abode_in_ny=True,
            abode_months_in_year=10,
            is_student_dorm=False,
            domiciled_in_ny=False,
        )
        assert r.status == "nonresident"
        assert "11 months" in r.reason or "duration" in r.reason

    def test_domicile_makes_resident_regardless(self):
        """Domicile in NY beats all other prongs."""
        r = evaluate(
            days_in_ny=10,
            has_permanent_abode_in_ny=False,
            abode_months_in_year=0,
            is_student_dorm=False,
            domiciled_in_ny=True,
            nyc_address=True,
        )
        assert r.status == "resident"
        assert r.nyc_resident is True

    def test_part_year_when_moved_into_ny(self):
        r = evaluate(
            days_in_ny=200,
            has_permanent_abode_in_ny=True,
            abode_months_in_year=6,
            is_student_dorm=False,
            domiciled_in_ny=False,
            moved_into_ny_mid_year=True,
        )
        assert r.status == "part_year"

    def test_no_abode_is_nonresident(self):
        r = evaluate(
            days_in_ny=20,
            has_permanent_abode_in_ny=False,
            abode_months_in_year=0,
            is_student_dorm=False,
            domiciled_in_ny=False,
        )
        assert r.status == "nonresident"
        assert "no permanent place of abode" in r.reason.lower()
