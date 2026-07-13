"""Tests for the Layer 9 Form Populator (Phase 3 architecture)."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from pypdf import PdfReader

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
        state.treaty.applied_benefits = [
            {
                "country_name": "China",
                "country_iso2": "CN",
                "article_id": "20(c)",
                "category": "student_personal_services",
                "explanation": "US-China treaty Article 20(c) wage exemption.",
                "exempt_amount": 5000.0,
                "applies_after_saving_clause": True,
                "requires_form_8833": True,
            }
        ]
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

    def test_it203_d_appended_only_when_ny_return_and_itemized(self, tmp_path):
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "X"
        state.identity.last_name = "Y"
        state.sch_a = {"total": 1500.0, "state_local_income_tax": 1500.0}
        state.forms_required = ["IT-203", "IT-203-B"]
        state.ready_for_assembly = True

        populator = FormPopulator(
            templates_dir=str(tmp_path / "templates"),
            outputs_dir=str(tmp_path / "out"),
            tax_year=2025,
        )
        outputs = populator.generate_filing_package(state)
        assert any("IT-203-D" in p for p in outputs)

    def test_it203_d_not_appended_without_ny_return(self, tmp_path):
        """No NY nexus (forms_required has no IT-203) -> no IT-203-D even
        if the federal itemized total is nonzero."""
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "X"
        state.identity.last_name = "Y"
        state.sch_a = {"total": 1500.0, "state_local_income_tax": 1500.0}
        state.ready_for_assembly = True

        populator = FormPopulator(
            templates_dir=str(tmp_path / "templates"),
            outputs_dir=str(tmp_path / "out"),
            tax_year=2025,
        )
        outputs = populator.generate_filing_package(state)
        assert not any("IT-203-D" in p for p in outputs)


class TestFormPopulatorVendoredTemplates:
    """When IRS fillable PDFs are vendored, the populator emits real PDF files
    (not JSON field-map fallbacks) and does not crash on the missing AcroForm
    dictionary.

    NOTE: filling the values requires the per-form ``*_fields.json`` remap
    (human-readable field_map keys -> IRS AcroForm field names); without those
    the produced PDFs are valid but currently unfilled. This test guards the
    file-emission path, not field-fill correctness.
    """

    def test_emits_pdf_not_json_when_templates_present(self):
        repo_templates = (
            Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"
        )
        if not (repo_templates / "f1040nr.pdf").exists():
            pytest.skip("IRS templates not vendored")

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

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent),
            outputs_dir=out,
            tax_year=2025,
        )
        generated = populator.generate_filing_package(state)

        pdfs = [p for p in generated if p.endswith(".pdf")]
        jsons = [p for p in generated if p.endswith(".fieldmap.json")]
        assert len(pdfs) > 0, "expected real PDF outputs when templates are present"
        assert len(jsons) == 0, "JSON fallback must not be used when templates vendored"

        for p in pdfs:
            assert open(p, "rb").read(5) == b"%PDF-"

        names = " ".join(os.path.basename(p) for p in pdfs)
        assert "1040-NR" in names
        assert "8843" in names


class TestFormPopulatorNYVendoredTemplates:
    """End-to-end check that the real IT-203/IT-203-B AcroForm PDFs are
    filled with correct values (not just emitted unfilled), including
    checkbox export-state resolution for the mangled-apostrophe MFS
    filing-status state baked into the real vendored PDF."""

    def test_it203_and_it203b_filled_with_real_values(self):
        repo_templates = (
            Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"
        )
        if not (repo_templates / "it203.pdf").exists():
            pytest.skip("NY IT-203 templates not vendored")

        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Mei"
        state.identity.last_name = "Zhang"
        state.identity.ssn = "123456789"
        state.identity.us_address_line1 = "100 Washington Sq"
        state.identity.us_city = "New York"
        state.identity.us_state = "NY"
        state.identity.us_zip = "10012"
        state.identity.filing_status = "single"
        state.income.total_w2_wages = 42000.0
        state.ny.ny_work_days = 200
        state.ny.total_work_days = 240
        state.ny.ny_source_wages = 35000.0
        state.ny.ny_source_income = 35000.0
        state.ny.ny_agi = 42000.0
        state.ny.ny_standard_deduction = 8000.0
        state.ny.ny_taxable_income = 34000.0
        state.ny.ny_tax_resident_basis = 1700.0
        state.ny.ny_income_percentage = 0.8333
        state.ny.ny_tax_apportioned = 1416.0
        state.ny.total_ny_state_local = 1416.0
        state.ny.ny_withholding = 900.0
        state.ny.ny_refund_or_owed = 1416.0 - 900.0
        state.forms_required = ["IT-203", "IT-203-B"]
        state.ready_for_assembly = True

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)

        it203_path = next(p for p in generated if p.endswith("IT-203.pdf"))
        it203b_path = next(p for p in generated if p.endswith("IT-203-B.pdf"))

        it203_values = {
            k: v.get("/V") for k, v in (PdfReader(it203_path).get_fields() or {}).items()
        }
        assert it203_values["Your first name"] == "Mei"
        assert it203_values["Your last name"] == "Zhang"
        assert it203_values["Filing Status"] == "/1 Single"
        assert it203_values["federal 1 dollars"] == "42000"
        assert it203_values["nys 1 dollars"] == "35000"

        it203b_values = {
            k: v.get("/V") for k, v in (PdfReader(it203b_path).get_fields() or {}).items()
        }
        assert it203b_values["lA"] == "200"
        assert it203b_values["hA"] == "240"

    def test_it203_mfs_checkbox_matches_mangled_apostrophe_export_state(self):
        """The real vendored PDF's MFS export state contains a mis-encoded
        apostrophe. The populator must emit that exact literal string, and
        pypdf's checkbox pass-through must resolve it to a real (non-Off)
        state, not silently fail to check the box."""
        repo_templates = (
            Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"
        )
        if not (repo_templates / "it203.pdf").exists():
            pytest.skip("NY IT-203 templates not vendored")

        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Raj"
        state.identity.last_name = "Patel"
        state.identity.filing_status = "mfs"
        state.identity.spouse_first_name = "Anjali"
        state.identity.spouse_last_name = "Patel"
        state.identity.spouse_ssn_or_itin = "912345678"
        state.forms_required = ["IT-203", "IT-203-B"]
        state.ready_for_assembly = True

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        it203_path = next(p for p in generated if p.endswith("IT-203.pdf"))

        fields = PdfReader(it203_path).get_fields() or {}
        filing_status_value = str(fields["Filing Status"].get("/V"))
        assert filing_status_value != "/Off"
        assert "Married Filing Seperate" in filing_status_value
        assert fields["Spouse's first name"].get("/V") == "Anjali"


class TestFormPopulator8833MultiRow:
    """Form 8833 must be filed once per treaty position (IRS requires a
    separate 8833 per item) — verify the per-row-cloning path actually
    produces N distinct, correctly-filled PDFs, not just N=1."""

    def test_two_benefits_produce_two_distinct_filled_pdfs(self):
        repo_templates = (
            Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"
        )
        if not (repo_templates / "f8833.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Wei"
        state.identity.last_name = "Chen"
        state.identity.itin = "912345678"
        state.forms_required = ["8833"]
        state.ready_for_assembly = True
        state.treaty.applied_benefits = [
            {
                "country_name": "China (People's Republic of)",
                "country_iso2": "CN",
                "article_id": "20(c)",
                "category": "student_personal_services",
                "explanation": "US-China treaty Article 20(c) wage exemption.",
                "exempt_amount": 5000.0,
                "applies_after_saving_clause": True,
                "requires_form_8833": True,
            },
            {
                "country_name": "China (People's Republic of)",
                "country_iso2": "CN",
                "article_id": "20(b)",
                "category": "scholarship_fellowship",
                "explanation": "US-China treaty Article 20(b) scholarship exemption.",
                "exempt_amount": 3000.0,
                "applies_after_saving_clause": False,
                "requires_form_8833": True,
            },
        ]

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)

        pdfs_8833 = sorted(p for p in generated if p.endswith(".pdf") and "8833" in p)
        assert len(pdfs_8833) == 2, f"expected 2 separate 8833 PDFs, got {pdfs_8833}"
        assert pdfs_8833[0] != pdfs_8833[1]

        def _real_values(path: str) -> dict:
            fields = PdfReader(path).get_fields() or {}
            return {
                k: v.get("/V")
                for k, v in fields.items()
                if v.get("/V") and str(v.get("/V")) not in ("/Off", "")
            }

        values_1 = _real_values(pdfs_8833[0])
        values_2 = _real_values(pdfs_8833[1])

        all_articles_seen = set()
        for vals in (values_1, values_2):
            all_articles_seen.update(v for v in vals.values() if v in ("20(c)", "20(b)"))
        assert all_articles_seen == {"20(c)", "20(b)"}, (
            "each row's own article must land in its own PDF, not be shared/"
            f"cross-contaminated — saw {all_articles_seen}"
        )

        all_amounts_seen = set()
        for vals in (values_1, values_2):
            all_amounts_seen.update(v for v in vals.values() if v in ("5000.0", "3000.0"))
        assert all_amounts_seen == {"5000.0", "3000.0"}
