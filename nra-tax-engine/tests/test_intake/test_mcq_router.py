"""Tests for the intake schema + MCQ router projection (Phase 6)."""

import pytest
from pydantic import ValidationError

from src.intake.intake_schema import (
    IntakeBanking,
    IntakeElections,
    IntakeExtras,
    IntakeFICA,
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

    def test_populate_state_seeds_employer_from_fica_intake(self):
        """Regression test: employer name/EIN typed into the FICA intake step
        must reach state (and from there, Forms 843/8316/IT-203-B) instead of
        being silently dropped."""
        payload = _full_payload()
        payload.fica = IntakeFICA(
            employer_attempted_refund=True,
            employer_name="New York University",
            employer_ein="13-5562308",
        )
        state = self.router.populate_state(payload)
        assert state.income.employer_name == "New York University"
        assert state.income.employer_ein == "13-5562308"

    def test_populate_state_seeds_elections_from_intake(self):
        """Regression test: elections typed at intake (§6013 election, large
        foreign gifts, closer-connection exception) must reach state so
        validate_post_l1 can block automatic assembly, instead of being
        silently dropped like the employer data was."""
        payload = _full_payload()
        payload.elections = IntakeElections(large_foreign_gifts_over_100k=True)
        state = self.router.populate_state(payload)
        assert state.elections.large_foreign_gifts_over_100k is True
        assert state.elections.section_6013g_election is False

    def test_populate_state_seeds_871d_election(self):
        payload = _full_payload()
        payload.elections = IntakeElections(section_871d_election=True)
        state = self.router.populate_state(payload)
        assert state.elections.section_871d_election is True

    def test_populate_state_seeds_banking_from_intake(self):
        """Regression test: direct-deposit routing/account data typed at
        intake must reach state.tax instead of being silently dropped —
        previously the real 1040-NR PDF fields for this existed but nothing
        wired the collected data to them."""
        payload = _full_payload()
        payload.banking = IntakeBanking(
            direct_deposit=True,
            routing_number="021000021",
            account_number="000123456789",
            account_type="checking",
        )
        state = self.router.populate_state(payload)
        assert state.tax.direct_deposit is True
        assert state.tax.routing_number == "021000021"
        assert state.tax.account_number == "000123456789"
        assert state.tax.account_type == "checking"

    def test_populate_state_seeds_visa_subtype_and_prior_residency(self):
        payload = _full_payload()
        payload.residency.visa_subtype = "teacher_researcher"
        payload.residency.prior_year_residency_status = "resident_alien"
        state = self.router.populate_state(payload)
        assert state.residency.visa_subtype == "teacher_researcher"
        assert state.residency.prior_year_residency_status == "resident_alien"

    def test_populate_state_seeds_prior_year_treaty_claim(self):
        payload = _full_payload()
        payload.income.prior_year_treaty_claim_total = 4500.0
        state = self.router.populate_state(payload)
        assert state.treaty.prior_year_treaty_claim_total == 4500.0

    def test_populate_state_seeds_fica_confirmation_flags(self):
        payload = _full_payload()
        payload.fica = IntakeFICA(employer_attempted_refund=True, has_form_8316=True)
        state = self.router.populate_state(payload)
        assert state.fica.employer_attempted_refund is True
        assert state.fica.has_form_8316 is True

    def test_populate_state_seeds_extras_from_intake(self):
        """Regression test: the extras step (13 real questions) must reach
        state instead of the frontend's buildIntakePayload() dropping the
        whole bucket before it's even sent."""
        payload = _full_payload()
        payload.extras = IntakeExtras(
            filed_previous_federal_return=True,
            made_estimated_federal_payments=True,
            estimated_federal_payment_amount=500.0,
            had_digital_assets=True,
        )
        state = self.router.populate_state(payload)
        assert state.extras.filed_previous_federal_return is True
        assert state.extras.made_estimated_federal_payments is True
        assert state.extras.estimated_federal_payment_amount == 500.0
        assert state.extras.had_digital_assets is True
        assert state.extras.is_full_time_student is False  # untouched default
