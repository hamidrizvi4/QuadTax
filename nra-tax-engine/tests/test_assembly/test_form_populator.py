"""Tests for the Layer 9 Form Populator (Phase 3 architecture)."""

import json
from pathlib import Path

import pytest

from src.assembly.form_populator import FormPopulator
from src.orchestrator.state import ReturnStateObject


class TestFormPopulatorGate:
    """The populator must refuse to run before the orchestrator finishes."""

    def test_not_ready_for_assembly_raises(self, tmp_path):
        state = ReturnStateObject(tax_year=2025)
        state.ready_for_assembly = False
        populator = FormPopulator(
            templates_dir=str(tmp_path),
            outputs_dir=str(tmp_path / "out"),
            tax_year=2025,
        )
        with pytest.raises(ValueError, match="not ready for assembly"):
            populator.generate_filing_package(state)


class TestFormPopulatorFieldMapFallback:
    """When templates are missing, the populator writes field-map JSON files."""

    def test_writes_fieldmap_json_for_missing_templates(self, tmp_path):
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Ming"
        state.identity.last_name = "Chen"
        state.identity.us_address_line1 = "123 Main St"
        state.identity.us_city = "Boston"
        state.identity.us_state = "MA"
        state.identity.us_zip = "02115"
        state.identity.country_of_citizenship = "CN"
        state.residency.exempt_visa_type = "F-1"
        state.residency.years_in_exempt_status = 2
        state.residency.spt_days_current_year = 300
        state.tax.total_tax_liability = 2762.0
        state.tax.total_withholding_credits = 4500.0
        state.tax.refund_or_owed = -1738.0
        state.forms_required = ["8833", "843"]
        state.ready_for_assembly = True

        populator = FormPopulator(
            templates_dir=str(tmp_path / "templates"),
            outputs_dir=str(tmp_path / "out"),
            tax_year=2025,
        )
        outputs = populator.generate_filing_package(state)

        # Every output should exist as a JSON fallback because templates are absent.
        assert len(outputs) > 0
        json_outputs = [Path(p) for p in outputs if p.endswith(".fieldmap.json")]
        assert len(json_outputs) == len(outputs)

        # Core forms are always produced.
        names = " ".join(outputs)
        assert "1040-NR" in names
        assert "Schedule-OI" in names
        assert "8843" in names
        assert "8833" in names
        assert "843" in names

        # Verify one of the fallbacks contains the expected field-map.
        f1040 = next(p for p in json_outputs if "1040-NR" in p.name)
        data = json.loads(f1040.read_text())
        assert data["last_name"] == "Chen"
        assert data["us_state"] == "MA"
        assert data["line_24_total_tax"] == "2762"


class TestFormPopulatorScheduleInjection:
    """Schedule-NEC is added automatically when FDAP > 0."""

    def test_sch_nec_appended_when_fdap_present(self, tmp_path):
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "X"
        state.identity.last_name = "Y"
        state.income.fdap_taxable_total = 5000.0
        state.tax.fdap_tax_liability = 700.0
        state.ready_for_assembly = True

        populator = FormPopulator(
            templates_dir=str(tmp_path / "templates"),
            outputs_dir=str(tmp_path / "out"),
            tax_year=2025,
        )
        outputs = populator.generate_filing_package(state)
        assert any("Schedule-NEC" in p for p in outputs)

    def test_sch_a_appended_when_itemized_present(self, tmp_path):
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "X"
        state.identity.last_name = "Y"
        state.sch_a = {"total": 1500.0, "state_local_income_tax": 1500.0, "disallowed_items": []}
        state.ready_for_assembly = True

        populator = FormPopulator(
            templates_dir=str(tmp_path / "templates"),
            outputs_dir=str(tmp_path / "out"),
            tax_year=2025,
        )
        outputs = populator.generate_filing_package(state)
        assert any("Schedule-A" in p for p in outputs)
