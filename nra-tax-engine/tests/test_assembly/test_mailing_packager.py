"""Tests for the mailing packager (Phase 5)."""

import json
from pathlib import Path

import pytest

from src.assembly.mailing_packager import (
    FEDERAL_ASSEMBLY_ORDER,
    NY_ASSEMBLY_ORDER,
    MailingPackager,
)
from src.orchestrator.state import ReturnStateObject


def _drop_field_maps(state: ReturnStateObject, forms_dir: Path) -> None:
    """Emit field-map JSONs into ``forms_dir`` so the packager has something to merge."""
    from src.assembly.form_populator import FormPopulator

    FormPopulator(
        templates_dir=str(forms_dir.parent / "missing_templates"),
        outputs_dir=str(forms_dir),
        tax_year=state.tax_year,
    ).generate_filing_package(state, output_dir=str(forms_dir))


def _build_china_art20c_nyu_state() -> ReturnStateObject:
    state = ReturnStateObject(tax_year=2025)
    state.identity.first_name = "Ming"
    state.identity.last_name = "Chen"
    state.identity.itin = "912345678"
    state.identity.us_address_line1 = "123 Beacon St"
    state.identity.us_city = "New York"
    state.identity.us_state = "NY"
    state.identity.us_zip = "10003"
    state.identity.filing_status = "single"
    state.residency.exempt_visa_type = "F-1"
    state.residency.years_in_exempt_status = 2
    state.residency.is_exempt_individual = True

    state.income.total_w2_wages = 30000.0
    state.income.eci_taxable_total = 30000.0

    state.treaty.is_eligible = True
    state.treaty.country = "CN"
    state.treaty.article_number = "20(c)"
    state.treaty.exempt_amount_applied = 5000.0
    state.treaty.applied_to_category = "student_personal_services"
    state.treaty.requires_form_8833 = True
    state.treaty.applied_benefits = [
        {
            "country_iso2": "CN",
            "country_name": "China",
            "article_id": "20(c)",
            "category": "student_personal_services",
            "exempt_amount": 5000.0,
            "rate_override": None,
            "applies_after_saving_clause": False,
            "requires_form_8833": True,
            "explanation": "Art 20(c) caps at $5k.",
        }
    ]

    state.fica.is_exempt = True
    state.fica.incorrect_ss_withheld = 1860.0
    state.fica.incorrect_medicare_withheld = 435.0
    state.fica.requires_form_843 = True

    state.tax.eci_tax_liability = 2762.0
    state.tax.total_tax_liability = 2762.0
    state.tax.total_withholding_credits = 4500.0
    state.tax.refund_or_owed = -1738.0
    state.withholding_report = {
        "federal_w2": 4500.0,
        "federal_1042s_ch3": 0.0,
        "federal_1042s_ch4": 0.0,
        "federal_1099": 0.0,
        "federal_estimated_payments": 0.0,
        "federal_total": 4500.0,
        "ss_withheld_w2": 1860.0,
        "medicare_withheld_w2": 435.0,
        "state_income_tax_w2": 1200.0,
        "local_income_tax_w2": 0.0,
        "sources_seen": ["W-2"],
    }

    state.ny.residency_status = "nonresident"
    state.ny.residency_reason = "Dorm exclusion (Knight)."
    state.ny.days_in_ny = 330
    state.ny.ny_source_wages = 30000.0
    state.ny.ny_source_income = 30000.0
    state.ny.ny_agi = 30000.0
    state.ny.ny_treaty_addback = 5000.0
    state.ny.ny_standard_deduction = 8000.0
    state.ny.ny_taxable_income = 22000.0
    state.ny.ny_tax_resident_basis = 1045.0
    state.ny.ny_income_percentage = 1.0
    state.ny.ny_tax_apportioned = 1045.0
    state.ny.nyc_tax = 0.0
    state.ny.yonkers_tax = 0.0
    state.ny.total_ny_state_local = 1045.0
    state.ny.ny_withholding = 1200.0
    state.ny.ny_refund_or_owed = -155.0

    state.forms_required = ["8833", "843", "IT-203", "IT-203-B"]
    state.ready_for_assembly = True
    return state


class TestAssemblyOrder:
    def test_federal_order_starts_with_1040nr(self):
        assert FEDERAL_ASSEMBLY_ORDER[0] == "1040-NR"

    def test_8843_precedes_w7_in_federal_order(self):
        assert FEDERAL_ASSEMBLY_ORDER.index("8843") < FEDERAL_ASSEMBLY_ORDER.index("W-7")

    def test_ny_order_resident_before_nonresident(self):
        assert NY_ASSEMBLY_ORDER.index("IT-201") < NY_ASSEMBLY_ORDER.index("IT-203")


class TestFederalPacket:
    def test_address_routes_no_payment_when_refund(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        assert pkg.federal.mailing_address["city_state_zip"].startswith("Austin")
        assert pkg.federal.has_payment is False

    def test_address_routes_balance_due(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        state.tax.refund_or_owed = 500.0  # owe $500
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        # Balance due routes to Charlotte unless W-7 forces ITIN Operations.
        assert "Charlotte" in pkg.federal.mailing_address["city_state_zip"]
        assert pkg.federal.has_payment is True

    def test_w7_overrides_to_itin_operations(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        state.forms_required.append("W-7")
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        assert pkg.federal.has_w7 is True
        assert "ITIN" in pkg.federal.mailing_address["line2"]

    def test_forms_in_order(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        ordered = pkg.federal.forms_in_order
        # 1040-NR first; Schedule-OI before 8843; 8833 before 8843 per Pub 519.
        assert ordered[0] == "1040-NR"
        assert ordered.index("Schedule-OI") < ordered.index("8843")
        assert ordered.index("8833") < ordered.index("8843")

    def test_cover_sheet_lists_forms_and_address(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        text = Path(pkg.federal.cover_sheet).read_text()
        assert "Ming Chen" in text
        assert "Austin" in text
        assert "1040-NR" in text
        assert "Federal refund" in text


class TestNYPacket:
    def test_ny_packet_built_when_it203_required(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        assert pkg.ny is not None
        assert "IT-203" in pkg.ny.forms_in_order
        assert pkg.ny.mailing_address["city_state_zip"].startswith("ALBANY")

    def test_no_ny_packet_when_no_it203(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        state.forms_required = [f for f in state.forms_required if not f.startswith("IT-")]
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        assert pkg.ny is None


class TestFICAPacket:
    def test_fica_843_packet_built(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        assert pkg.fica_843 is not None
        # 843 mails to Cincinnati per current IRS guidance.
        assert pkg.fica_843.mailing_address["city_state_zip"].startswith("Cincinnati")
        text = Path(pkg.fica_843.cover_sheet).read_text()
        assert "Form 8316" in text
        assert "SEPARATELY" in text

    def test_no_fica_packet_when_not_exempt(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        state.fica.requires_form_843 = False
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        assert pkg.fica_843 is None


class TestJSONManifestFallback:
    def test_fallback_when_no_pdfs(self, tmp_path):
        state = _build_china_art20c_nyu_state()
        forms_dir = tmp_path / "forms"
        forms_dir.mkdir()
        _drop_field_maps(state, forms_dir)  # writes JSON only

        pkg = MailingPackager(tax_year=2025).assemble(state, forms_dir, tmp_path / "out")
        # No PDFs available → packets emit JSON manifests.
        assert pkg.federal.pdf_output is None
        assert pkg.federal.json_output is not None
        manifest = json.loads(Path(pkg.federal.json_output).read_text())
        assert manifest["_assembly_order"][0] == "1040-NR"
        assert "1040-NR" in manifest["forms"]
