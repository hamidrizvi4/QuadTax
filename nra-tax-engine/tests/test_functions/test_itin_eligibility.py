"""Tests for ITIN eligibility (Form W-7 triggering)."""

from src.functions.itin_eligibility import evaluate


class TestITINEligibility:
    def test_has_ssn_no_w7_needed(self):
        r = evaluate(has_ssn=True, has_existing_itin=False)
        assert r.needs_w7 is False
        assert r.reason_code is None

    def test_no_ssn_no_itin_student_first_time(self):
        r = evaluate(has_ssn=False, has_existing_itin=False, is_student=True)
        assert r.needs_w7 is True
        assert r.reason_code == "f"
        assert r.is_renewal is False
        assert "first-time" in r.explanation.lower()

    def test_no_ssn_treaty_benefit_drives_reason_a(self):
        r = evaluate(
            has_ssn=False, has_existing_itin=False, claiming_treaty_benefit=True
        )
        assert r.reason_code == "a"

    def test_existing_itin_unused_3_years_requires_renewal(self):
        r = evaluate(
            has_ssn=False,
            has_existing_itin=True,
            itin_last_used_on_return_year=2021,
            current_tax_year=2025,
        )
        assert r.needs_w7 is True
        assert r.is_renewal is True
        assert "renewal" in r.explanation.lower()

    def test_existing_itin_recently_used_no_w7(self):
        r = evaluate(
            has_ssn=False,
            has_existing_itin=True,
            itin_last_used_on_return_year=2024,
            current_tax_year=2025,
        )
        assert r.needs_w7 is False
        assert r.is_renewal is False
