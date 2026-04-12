"""Tests for the ReturnStateObject and its sub-models."""

import pytest

from src.orchestrator.state import (
    FicaState,
    IncomeState,
    ResidencyState,
    ReturnStateObject,
    TaxCalculatedState,
    TreatyState,
)


class TestResidencyState:
    """Test suite for the ResidencyState sub-model."""

    def test_defaults(self):
        """ResidencyState initializes with safe pending defaults."""
        r = ResidencyState()
        assert r.status == "pending"
        assert r.spt_days_current_year == 0
        assert r.exempt_visa_type is None
        assert r.years_in_exempt_status == 0
        assert r.is_exempt_individual is False

    def test_valid_statuses(self):
        """All four Literal statuses are accepted."""
        for status in ("nonresident_alien", "resident_alien", "dual_status", "pending"):
            r = ResidencyState(status=status)
            assert r.status == status

    def test_invalid_status_rejected(self):
        """An invalid status string is rejected by Pydantic."""
        with pytest.raises(Exception):
            ResidencyState(status="unknown_status")

    def test_exempt_individual_f1(self):
        """F-1 student within 5-year window should be marked exempt."""
        r = ResidencyState(
            status="nonresident_alien",
            exempt_visa_type="F-1",
            years_in_exempt_status=3,
            is_exempt_individual=True,
            spt_days_current_year=0,
        )
        assert r.is_exempt_individual is True
        assert r.exempt_visa_type == "F-1"

    def test_spt_days_bounds(self):
        """spt_days_current_year must be 0–366."""
        with pytest.raises(Exception):
            ResidencyState(spt_days_current_year=-1)
        with pytest.raises(Exception):
            ResidencyState(spt_days_current_year=400)
        # Boundary values are fine
        assert ResidencyState(spt_days_current_year=0).spt_days_current_year == 0
        assert ResidencyState(spt_days_current_year=366).spt_days_current_year == 366


class TestIncomeState:
    """Test suite for the IncomeState sub-model."""

    def test_defaults(self):
        """All income amounts default to zero."""
        inc = IncomeState()
        assert inc.total_w2_wages == 0.0
        assert inc.total_1042s_gross == 0.0
        assert inc.eci_taxable_total == 0.0
        assert inc.fdap_taxable_total == 0.0
        assert inc.exempt_scholarship_total == 0.0

    def test_typical_f1_student(self):
        """Typical F-1 student with W-2 wages and a scholarship."""
        inc = IncomeState(
            total_w2_wages=12000.0,
            total_1042s_gross=8000.0,
            eci_taxable_total=12000.0,
            fdap_taxable_total=0.0,
            exempt_scholarship_total=8000.0,
        )
        assert inc.total_w2_wages == 12000.0
        assert inc.exempt_scholarship_total == 8000.0

    def test_negative_income_rejected(self):
        """Income amounts must be non-negative."""
        with pytest.raises(Exception):
            IncomeState(total_w2_wages=-100.0)


class TestTreatyState:
    """Test suite for the TreatyState sub-model."""

    def test_defaults(self):
        """Treaty defaults to ineligible."""
        t = TreatyState()
        assert t.is_eligible is False
        assert t.country is None
        assert t.article_number is None
        assert t.exempt_amount_applied == 0.0

    def test_india_treaty_21_2(self):
        """India treaty Article 21(2) — $5,000 student wage exemption."""
        t = TreatyState(
            is_eligible=True,
            country="IN",
            article_number="21(2)",
            exempt_amount_applied=5000.0,
        )
        assert t.is_eligible is True
        assert t.country == "IN"
        assert t.article_number == "21(2)"
        assert t.exempt_amount_applied == 5000.0


class TestFicaState:
    """Test suite for the FicaState sub-model."""

    def test_defaults(self):
        """FICA defaults to non-exempt with no amounts."""
        f = FicaState()
        assert f.is_exempt is False
        assert f.incorrect_ss_withheld == 0.0
        assert f.incorrect_medicare_withheld == 0.0
        assert f.requires_form_843 is False

    def test_fica_refund_scenario(self):
        """F-1 student who was incorrectly withheld FICA."""
        f = FicaState(
            is_exempt=True,
            incorrect_ss_withheld=3100.00,
            incorrect_medicare_withheld=725.00,
            requires_form_843=True,
        )
        assert f.requires_form_843 is True
        assert f.incorrect_ss_withheld + f.incorrect_medicare_withheld == 3825.0


class TestTaxCalculatedState:
    """Test suite for the TaxCalculatedState sub-model."""

    def test_defaults(self):
        """All tax amounts default to zero."""
        t = TaxCalculatedState()
        assert t.eci_tax_liability == 0.0
        assert t.fdap_tax_liability == 0.0
        assert t.total_tax_liability == 0.0
        assert t.total_withholding_credits == 0.0
        assert t.refund_or_owed == 0.0

    def test_refund_scenario(self):
        """Positive refund_or_owed means a refund is due."""
        t = TaxCalculatedState(
            eci_tax_liability=500.0,
            total_tax_liability=500.0,
            total_withholding_credits=1200.0,
            refund_or_owed=700.0,
        )
        assert t.refund_or_owed > 0

    def test_owed_scenario(self):
        """Negative refund_or_owed means tax is owed."""
        t = TaxCalculatedState(
            total_tax_liability=3000.0,
            total_withholding_credits=1000.0,
            refund_or_owed=-2000.0,
        )
        assert t.refund_or_owed < 0


class TestReturnStateObject:
    """Test suite for the master state object."""

    def test_default_initialization(self):
        """State should initialize with sensible defaults (no crashes)."""
        state = ReturnStateObject()
        assert state.residency is not None
        assert state.income is not None
        assert state.treaty is not None
        assert state.fica is not None
        assert state.tax is not None
        assert state.forms_required == []
        assert state.ready_for_assembly is False
        assert state.completed_layers == []

    def test_mark_layer_complete(self):
        """Marking a layer complete should add it to the list."""
        state = ReturnStateObject()
        state.mark_layer_complete("L1")
        assert state.is_layer_complete("L1")
        assert not state.is_layer_complete("L3")

    def test_no_duplicate_layer_marking(self):
        """Marking the same layer twice should not create duplicates."""
        state = ReturnStateObject()
        state.mark_layer_complete("L1")
        state.mark_layer_complete("L1")
        assert state.completed_layers.count("L1") == 1

    def test_full_state_serialization(self):
        """The full state object should serialize to and from JSON."""
        state = ReturnStateObject()
        state.residency.status = "nonresident_alien"
        state.income.total_w2_wages = 25000.0
        state.treaty.country = "IN"
        state.forms_required = ["1040-NR", "8843"]
        state.mark_layer_complete("L1")

        json_str = state.model_dump_json()
        restored = ReturnStateObject.model_validate_json(json_str)

        assert restored.residency.status == "nonresident_alien"
        assert restored.income.total_w2_wages == 25000.0
        assert restored.treaty.country == "IN"
        assert restored.forms_required == ["1040-NR", "8843"]
        assert restored.is_layer_complete("L1")

    def test_forms_required_list(self):
        """forms_required should accept a list of form identifiers."""
        state = ReturnStateObject(forms_required=["1040-NR", "8843", "843", "IT-203"])
        assert len(state.forms_required) == 4
        assert "843" in state.forms_required

    def test_ready_for_assembly_gate(self):
        """ready_for_assembly defaults to False and can be set True."""
        state = ReturnStateObject()
        assert state.ready_for_assembly is False
        state.ready_for_assembly = True
        assert state.ready_for_assembly is True

    def test_mutate_sub_model(self):
        """Sub-models should be mutable in place."""
        state = ReturnStateObject()
        state.residency.status = "nonresident_alien"
        state.residency.spt_days_current_year = 120
        state.residency.exempt_visa_type = "F-1"
        state.residency.is_exempt_individual = True

        assert state.residency.status == "nonresident_alien"
        assert state.residency.spt_days_current_year == 120
