"""Tests for the intake schema + MCQ router projection (Phase 6)."""

import pytest
from pydantic import ValidationError

from src.intake.intake_schema import (
    IntakeIdentity,
    IntakeIncome,
    IntakeNYContext,
    IntakePayload,
    IntakeResidency,
)
from src.intake.mcq_router import MCQRouter


def _full_payload() -> IntakePayload:
    return IntakePayload(
        identity=IntakeIdentity(
            first_name="Ming",
            last_name="Chen",
            itin="912345678",
            country_of_citizenship="CN",
            country_of_tax_residence="CN",
            passport_number="E12345678",
            passport_country="CN",
            us_address_line1="123 Beacon St",
            us_city="New York",
            us_state="NY",
            us_zip="10003",
            occupation="Graduate Student",
            filing_status="single",
        ),
        residency=IntakeResidency(
            tax_year=2025,
            visa_type="F-1",
            first_us_arrival_year=2024,
        ),
        income=IntakeIncome(
            income_description="On-campus dining hall worker",
            requires_services=True,
            is_qualified_expense=False,
        ),
        ny=IntakeNYContext(
            days_in_ny=330,
            has_permanent_abode_in_ny=True,
            abode_months_in_year=12,
            is_student_dorm=True,
            ny_work_days=200,
            total_work_days=200,
            employer_in_ny=True,
            institution_1042s_in_ny=True,
        ),
    )


class TestIntakeSchema:
    def test_minimal_payload_validates(self):
        payload = IntakePayload(
            identity=IntakeIdentity(),
            residency=IntakeResidency(),
            income=IntakeIncome(),
        )
        assert payload.identity.filing_status == "single"
        assert payload.ny is None  # NY is optional

    def test_invalid_filing_status_rejected(self):
        with pytest.raises(ValidationError):
            IntakeIdentity(filing_status="mfj")  # NRA cannot file MFJ

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            IntakeIdentity(bogus_field="x")  # type: ignore[call-arg]

    def test_tax_year_lower_bound(self):
        with pytest.raises(ValidationError):
            IntakeResidency(tax_year=2023)


class TestMCQRouter:
    def setup_method(self):
        self.router = MCQRouter()

    def test_populate_state_seeds_identity(self):
        payload = _full_payload()
        state = self.router.populate_state(payload)
        assert state.identity.first_name == "Ming"
        assert state.identity.last_name == "Chen"
        assert state.identity.itin == "912345678"
        assert state.identity.us_state == "NY"
        assert state.identity.filing_status == "single"
        assert state.tax_year == 2025

    def test_populate_state_seeds_residency_visa(self):
        payload = _full_payload()
        state = self.router.populate_state(payload)
        assert state.residency.exempt_visa_type == "F-1"

    def test_to_mcq_answers_legacy_shape(self):
        payload = _full_payload()
        mcq = self.router.to_mcq_answers(payload)
        assert mcq["tax_year"] == 2025
        assert mcq["visa_type"] == "F-1"
        assert mcq["first_us_arrival_year"] == 2024
        assert mcq["tax_residence_country"] == "CN"
        assert mcq["requires_services"] is True
        assert mcq["is_qualified_expense"] is False
        # NY block surfaces nested when present.
        assert "ny_intake" in mcq
        assert mcq["ny_intake"]["days_in_ny"] == 330

    def test_to_mcq_answers_omits_ny_when_absent(self):
        payload = IntakePayload(
            identity=IntakeIdentity(),
            residency=IntakeResidency(),
            income=IntakeIncome(),
        )
        mcq = self.router.to_mcq_answers(payload)
        assert "ny_intake" not in mcq

    def test_state_can_drive_a_form_populator(self):
        """Smoke-test: populated state should feed the form registry without errors."""
        from src.assembly.forms import compute

        payload = _full_payload()
        state = self.router.populate_state(payload)
        state.ready_for_assembly = True
        f1040 = compute("1040-NR", state)
        assert f1040["last_name"] == "Chen"
        assert f1040["us_state"] == "NY"
        assert f1040["identifying_number"] == "912345678"
