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


class TestFormPopulator1040NRVendoredTemplate:
    """End-to-end check that the real core Form 1040-NR AcroForm PDF
    (``topmostSubform[0].Page1[0]...`` / ``Page2[0]...`` hierarchy — do not
    confuse with Schedule OI's separate ``form1040-NR[0]...`` hierarchy) is
    filled with correct, internally-consistent values, including several
    lines that were confirmed-broken during a rigorous field-by-field audit:
    AMT never reaching the form (wrong state attribute), line 1a reporting
    gross instead of treaty-net wages, and FDAP income being double-counted
    onto line 8 instead of flowing through line 23a."""

    def _templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"

    def _build_state(self) -> ReturnStateObject:
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Ming"
        state.identity.middle_initial = "Q"
        state.identity.last_name = "Chen"
        state.identity.itin = "912345678"
        state.identity.us_address_line1 = "123 Beacon St Apt 4"
        state.identity.us_city = "Boston"
        state.identity.us_state = "MA"
        state.identity.us_zip = "02115"
        state.identity.filing_status = "single"
        state.identity.occupation = "Graduate Student"

        state.income.total_w2_wages = 30000.0
        state.income.eci_taxable_total = 30000.0
        state.income.fdap_taxable_total = 5000.0

        state.treaty.applied_benefits = [
            {
                "country_iso2": "CN", "country_name": "China (People's Republic of)",
                "article_id": "20(c)", "category": "student_personal_services",
                "exempt_amount": 5000.0, "requires_form_8833": True,
                "explanation": "US-China treaty Article 20(c) wage exemption.",
            }
        ]

        state.tax.agi = 25000.0
        state.tax.taxable_income = 25000.0
        state.tax.eci_tax_liability = 2200.0
        state.tax.fdap_tax_liability = 700.0
        state.tax.total_tax_liability = 2900.0
        state.tax.total_withholding_credits = 4500.0
        state.tax.refund_or_owed = -1600.0

        state.amt = {"amti": 40000.0, "exemption": 30000.0, "amt_owed": 300.0, "binds": True}
        state.estimated_tax_penalty = {"penalty_amount": 15.0, "safe_harbor_met": False}
        state.withholding_report = {
            "federal_w2": 4000.0,
            "federal_1042s_ch3": 400.0,
            "federal_1042s_ch4": 0.0,
            "federal_1099": 100.0,
            "federal_estimated_payments": 0.0,
            "federal_total": 4500.0,
            "sources_seen": ["W-2", "1042-S", "1099"],
        }
        state.forms_required = []
        state.ready_for_assembly = True
        return state

    def _generate(self, state: ReturnStateObject) -> dict:
        repo_templates = self._templates_dir()
        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        pdf_path = next(p for p in generated if p.endswith("1040-NR.pdf"))
        fields = PdfReader(pdf_path).get_fields() or {}
        return {k: v.get("/V") for k, v in fields.items()}

    def test_amt_and_fdap_flow_through_with_full_line_by_line_consistency(self):
        """AMT (line 17) and FDAP/Schedule-NEC tax (line 23a) must both
        reach the real PDF and the intermediate arithmetic lines (18, 22,
        23d, 24) must actually sum correctly, not just the final total."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nr.pdf").exists():
            pytest.skip("IRS templates not vendored")

        values = self._generate(self._build_state())

        def v(field: str) -> str:
            return values[f"topmostSubform[0].{field}"]

        # Line 1a/1k/1z — wages net of the $5,000 treaty exemption.
        assert v("Page1[0].f1_42[0]") == "25000"
        assert v("Page1[0].Line1k_ReadOrder[0].f1_53[0]") == "5000"
        assert v("Page1[0].f1_54[0]") == "25000"
        # Line 9/11a/11b — all mirror the authoritative AGI.
        assert v("Page1[0].f1_69[0]") == "25000"
        assert v("Page1[0].f1_71[0]") == "25000"
        assert v("Page2[0].f2_01[0]") == "25000"
        # Line 15/16 — taxable income / ECI tax.
        assert v("Page2[0].f2_07[0]") == "25000"
        assert v("Page2[0].f2_09[0]") == "2200"
        # Line 17 (AMT) — confirmed-broken bug: used to always be blank.
        assert v("Page2[0].f2_10[0]") == "300"
        # Line 18 = 16 + 17.
        assert v("Page2[0].f2_11[0]") == "2500"
        # Line 22 = 18 (credits unmodeled/0).
        assert v("Page2[0].f2_15[0]") == "2500"
        # Line 23a (FDAP/Schedule NEC tax) — confirmed-broken bug: used to
        # be entirely unmapped despite a real nonzero dollar figure.
        assert v("Page2[0].Line23a_ReadOrder[0].f2_16[0]") == "700"
        # Line 23b (self-employment/other Sch 2 taxes) — genuinely unmodeled.
        assert values.get("topmostSubform[0].Page2[0].f2_17[0]") in (None, "")
        # Line 23d = 23a + 23b(0) + 23c(0).
        assert v("Page2[0].f2_19[0]") == "700"
        # Line 24 = 22 + 23d = 2500 + 700 = 3200 (== total_tax_liability(2900) + amt(300)).
        assert v("Page2[0].f2_20[0]") == "3200"
        # Line 25a/25b/25d/25g withholding.
        assert v("Page2[0].Line25_ReadOrder[0].f2_21[0]") == "4000"
        assert v("Page2[0].f2_22[0]") == "100"
        assert v("Page2[0].f2_24[0]") == "4100"
        assert v("Page2[0].f2_27[0]") == "400"
        # Line 33 total payments.
        assert v("Page2[0].f2_35[0]") == "4500"
        # Line 38 estimated tax penalty — confirmed-broken bug: used to be unmapped.
        assert v("Page2[0].f2_43[0]") == "15"

        # Line 8 must never carry the FDAP amount (double-count regression guard).
        # (No AcroForm key targets line 8 anymore since the mapping was removed;
        # nothing to assert here beyond line 9 not being inflated, checked above.)

    def test_no_amt_no_fdap_leaves_those_lines_genuinely_blank_not_zero(self):
        """When there's no AMT and no FDAP income, lines 17/23a/23d/38 must
        render as blank (per IRS whole-dollar convention for $0), never a
        stray "0" and never a wrong fallback value."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nr.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.income.fdap_taxable_total = 0.0
        state.tax.fdap_tax_liability = 0.0
        state.tax.total_tax_liability = 2200.0
        state.amt = {}
        state.estimated_tax_penalty = {}

        values = self._generate(state)

        def v(field: str) -> str:
            return values.get(f"topmostSubform[0].{field}")

        assert v("Page2[0].f2_10[0]") in (None, "")  # line 17 AMT
        assert v("Page2[0].Line23a_ReadOrder[0].f2_16[0]") in (None, "")  # line 23a FDAP
        assert v("Page2[0].f2_19[0]") in (None, "")  # line 23d
        assert v("Page2[0].f2_43[0]") in (None, "")  # line 38 penalty
        assert v("Page2[0].f2_20[0]") == "2200"  # line 24 == eci tax only

    def test_filing_status_and_digital_assets_checkboxes_resolve_real_states(self):
        """Independent single-state checkboxes (not a shared radio group at
        the PDF level) — confirm both the checked box shows its real export
        state and the sibling boxes show "/Off", never the wrong fallback."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nr.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.identity.filing_status = "mfs"
        state.extras.had_digital_assets = True
        values = self._generate(state)

        assert values["topmostSubform[0].Page1[0].c1_5[0]"] == "/Off"  # Single
        assert values["topmostSubform[0].Page1[0].c1_5[1]"] == "/2"  # MFS (real export state)
        assert values["topmostSubform[0].Page1[0].c1_5[2]"] == "/Off"  # QSS
        assert values["topmostSubform[0].Page1[0].c1_6[0]"] == "/1"  # Digital assets: Yes
        assert values["topmostSubform[0].Page1[0].c1_6[1]"] == "/Off"  # Digital assets: No

    def test_direct_deposit_checking_and_savings_resolve_real_states(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nr.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.tax.direct_deposit = True
        state.tax.routing_number = "021000021"
        state.tax.account_number = "000123456789"
        state.tax.account_type = "checking"
        values = self._generate(state)
        assert values["topmostSubform[0].Page2[0].c2_6[0]"] == "/1"  # Checking
        assert values["topmostSubform[0].Page2[0].c2_6[1]"] == "/Off"  # Savings
        assert values["topmostSubform[0].Page2[0].RoutingNo[0].f2_38[0]"] == "021000021"
        assert values["topmostSubform[0].Page2[0].AccountNo[0].f2_39[0]"] == "000123456789"

        state2 = self._build_state()
        state2.tax.direct_deposit = True
        state2.tax.account_type = "savings"
        values2 = self._generate(state2)
        assert values2["topmostSubform[0].Page2[0].c2_6[0]"] == "/Off"
        assert values2["topmostSubform[0].Page2[0].c2_6[1]"] == "/2"  # Savings (real export state)


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

    def test_it203b_line_1n_and_schedule_b_through_real_ny_agent(self):
        """End-to-end regression covering two IT-203-B bugs, driven through
        the real NYAgent (not hand-set state) so the full intake -> state ->
        PDF pipeline is exercised:

        1. line 1n must reflect ny_source_allocator.allocate()'s actual
           apportionment (0 for a non-NY employer), not just the raw
           ny_work_days/total_work_days ratio, so 1n x 1o == 1p on the
           real filled PDF.
        2. Schedule B's address block must be gated on abode_months_in_year
           (living quarters actually maintained), not days_in_ny (mere
           physical-presence days) -- a filer who never maintained NY
           living quarters must not get an address row even with a large
           days_in_ny count.
        """
        from src.agents.l9_ny import NYAgent

        repo_templates = (
            Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"
        )
        if not (repo_templates / "it203b.pdf").exists():
            pytest.skip("NY IT-203-B template not vendored")

        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Arjun"
        state.identity.last_name = "Rao"
        state.identity.ssn = "123456789"
        state.identity.us_address_line1 = "10 Astor Pl"
        state.identity.us_city = "New York"
        state.identity.us_state = "NY"
        state.identity.us_zip = "10003"
        state.identity.filing_status = "single"
        state.income.total_w2_wages = 50000.0
        state.forms_required = ["IT-203", "IT-203-B"]
        state.ready_for_assembly = True

        NYAgent().process_ny(
            state,
            {
                "ny_work_days": 120,
                "total_work_days": 240,
                "employer_in_ny": False,  # remote job for an out-of-state employer
                "days_in_ny": 300,  # physically present a lot ...
                "has_permanent_abode_in_ny": False,
                "abode_months_in_year": 0,  # ... but never leased/maintained NY housing
                "is_student_dorm": False,
            },
        )
        assert state.ny.ny_source_wages == 0.0  # sanity: allocate() zeroed it out

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        it203b_path = next(p for p in generated if p.endswith("IT-203-B.pdf"))
        values = {
            k: v.get("/V") for k, v in (PdfReader(it203b_path).get_fields() or {}).items()
        }

        assert values["lA"] == "120"  # real physical NY work days, unaffected
        assert values["1n2A"] == "0.0000"  # NOT 120/240 = 0.5000
        assert values["p dollarsA"] == "0"
        assert values.get("Col A1 - address") is None
        assert values.get("Col B1 - City") is None
        assert values.get("ZIP1") is None
        assert values.get("Col E1 - box.0") in (None, "/Off")
        assert values["days"] == "300"  # days_in_ny is still reported on its own line

    @staticmethod
    def _real_widget_export_states(pdf_path: Path, field_name: str) -> set:
        """Dump the REAL /AP /N export states for a field's widget
        annotations directly from the raw PDF structure — not
        ``reader.get_fields()``'s ``/_States_``, which the module docstrings
        throughout this codebase document as unreliable for multi-kid radio
        groups (it collapses to a generic ``/1``/``/Off`` guess instead of
        the field's actual defined states)."""

        def _fq_name(obj) -> str:
            parts = []
            cur = obj
            while cur is not None:
                t = cur.get("/T")
                if t:
                    parts.append(str(t))
                parent = cur.get("/Parent")
                cur = parent.get_object() if parent else None
            return ".".join(reversed(parts))

        reader = PdfReader(str(pdf_path))
        states: set = set()
        for page in reader.pages:
            for annot in page.get("/Annots") or []:
                obj = annot.get_object()
                if obj.get("/Subtype") != "/Widget" or _fq_name(obj) != field_name:
                    continue
                ap = obj.get("/AP")
                if ap and "/N" in ap:
                    n_obj = ap["/N"].get_object()
                    if hasattr(n_obj, "keys"):
                        states.update(n_obj.keys())
        return states

    def test_it203_mfs_checkbox_matches_mangled_apostrophe_export_state(self):
        """The real vendored PDF's MFS export state contains a mis-encoded
        apostrophe (a single mangled CJK codepoint standing in for "'s",
        with no separate "s" character after it). The populator must emit
        that EXACT literal string — verified here against the real
        widget's own /AP/N export states dumped straight from the PDF, not
        just "isn't /Off" — or pypdf's checkbox pass-through silently
        writes an unrecognized value and the MFS box renders unchecked/
        broken despite /V looking superficially plausible."""
        repo_templates = (
            Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"
        )
        template_path = repo_templates / "it203.pdf"
        if not template_path.exists():
            pytest.skip("NY IT-203 templates not vendored")

        real_states = self._real_widget_export_states(template_path, "Filing Status")
        assert real_states, "could not read real Filing Status export states from template"

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
        # The decisive check: the written value must be byte-for-byte one
        # of the field's real, defined export states — not merely
        # non-"/Off" and superficially plausible (a mismatched string with
        # an extra stray "s" would still pass the two asserts above while
        # rendering the checkbox unchecked/broken in an actual viewer).
        assert filing_status_value in real_states
        assert fields["Spouse's first name"].get("/V") == "Anjali"


class TestFormPopulatorScheduleOIVendoredTemplate:
    """End-to-end check that the real Schedule OI AcroForm PDF is filled
    with correct values against the real field structure — the TY2025
    revision reshuffled every item letter compared to older Schedule OI
    revisions (e.g. its Item C/D/F/J/K questions didn't exist before, and
    its Item E/H/I/L/M meant different things before), so this guards
    against regressing to a stale field mapping."""

    def _templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"

    def test_header_and_identity_fields_filled(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nro.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Ming"
        state.identity.middle_initial = "Q"
        state.identity.last_name = "Chen"
        state.identity.itin = "912345678"
        state.identity.country_of_citizenship = "CN"
        state.identity.country_of_tax_residence = "CN"
        state.residency.exempt_visa_type = "F-1"
        state.residency.days_present_current_year = 300
        state.residency.days_present_year_minus_1 = 365
        state.residency.days_present_year_minus_2 = 10
        state.forms_required = []
        state.ready_for_assembly = True

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        oi_path = next(p for p in generated if p.endswith("Schedule-OI.pdf"))
        values = {
            k: v.get("/V") for k, v in (PdfReader(oi_path).get_fields() or {}).items()
        }

        # Header — every attached schedule must repeat name + identifying number.
        assert values["form1040-NR[0].Page1[0].f1_1[0]"] == "Ming Q Chen"
        assert values["form1040-NR[0].Page1[0].f1_2[0]"] == "912345678"
        # Item A/B — country of citizenship / tax residence.
        assert values["form1040-NR[0].Page1[0].f1_3[0]"] == "CN"
        assert values["form1040-NR[0].Page1[0].f1_4[0]"] == "CN"
        # Item E (NOT "C" — see schedule_oi.py's field-letter map) — visa type.
        assert values["form1040-NR[0].Page1[0].f1_5[0]"] == "F-1"
        # Item H (NOT "G") — 3-year day count, oldest-to-newest left to right.
        assert values["form1040-NR[0].Page1[0].f1_23[0]"] == "10"
        assert values["form1040-NR[0].Page1[0].f1_24[0]"] == "365"
        assert values["form1040-NR[0].Page1[0].f1_25[0]"] == "300"

    def test_item_i_checkbox_pair_resolves_real_export_states_both_ways(self):
        """c1_6[0]/c1_6[1] are independent checkbox fields with real export
        states "/1" and "/2" (verified against the vendored PDF's widget
        annotations) — confirm both a True and a False answer land on a
        real checked state, never a fabricated "/1" fallback or a blank
        pair that reads as unanswered."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nro.pdf").exists():
            pytest.skip("IRS templates not vendored")

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )

        def _oi_checkbox_values(filed_prior_year: bool) -> dict:
            state = ReturnStateObject(tax_year=2025)
            state.identity.first_name = "Ming"
            state.identity.last_name = "Chen"
            state.extras.filed_previous_federal_return = filed_prior_year
            state.forms_required = []
            state.ready_for_assembly = True
            generated = populator.generate_filing_package(state)
            oi_path = next(p for p in generated if p.endswith("Schedule-OI.pdf"))
            fields = PdfReader(oi_path).get_fields() or {}
            return {
                "yes": fields["form1040-NR[0].Page1[0].c1_6[0]"].get("/V"),
                "no": fields["form1040-NR[0].Page1[0].c1_6[1]"].get("/V"),
            }

        checked_yes = _oi_checkbox_values(True)
        assert checked_yes["yes"] == "/1"
        assert checked_yes["no"] == "/Off"

        checked_no = _oi_checkbox_values(False)
        assert checked_no["yes"] == "/Off"
        assert checked_no["no"] == "/2"

    def test_treaty_table_multi_row_and_total_excludes_scholarship(self):
        """Verify all 3 printed row slots fill with distinct data (not just
        one row) and that the (e) Total field mirrors 1040-NR line 1k's
        wage-only filter rather than summing every row shown in the table."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nro.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Wei"
        state.identity.last_name = "Zhang"
        state.identity.itin = "912345678"
        state.treaty.applied_benefits = [
            {
                "country_iso2": "CN", "country_name": "China (People's Republic of)",
                "article_id": "20(c)", "category": "student_personal_services",
                "exempt_amount": 2000.0,
            },
            {
                "country_iso2": "CN", "country_name": "China (People's Republic of)",
                "article_id": "19", "category": "teaching_research",
                "exempt_amount": 3000.0,
            },
            {
                "country_iso2": "CN", "country_name": "China (People's Republic of)",
                "article_id": "20(b)", "category": "scholarship_fellowship",
                "exempt_amount": 4000.0,
            },
        ]
        state.forms_required = []
        state.ready_for_assembly = True

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        oi_path = next(p for p in generated if p.endswith("Schedule-OI.pdf"))
        values = {
            k: v.get("/V") for k, v in (PdfReader(oi_path).get_fields() or {}).items()
        }

        row_prefix = "form1040-NR[0].Page1[0].LineL1_Table[0]"
        assert values[f"{row_prefix}.BodyRow1[0].f1_28[0]"] == "20(c)"
        assert values[f"{row_prefix}.BodyRow1[0].f1_30[0]"] == "2000.0"
        assert values[f"{row_prefix}.BodyRow2[0].f1_32[0]"] == "19"
        assert values[f"{row_prefix}.BodyRow2[0].f1_34[0]"] == "3000.0"
        assert values[f"{row_prefix}.BodyRow3[0].f1_36[0]"] == "20(b)"
        assert values[f"{row_prefix}.BodyRow3[0].f1_38[0]"] == "4000.0"
        # (e) Total = 2000 + 3000 (wage-category only) — the scholarship
        # row's 4000 is disclosed in the table but excluded from the total
        # that flows to 1040-NR line 1k.
        assert values["form1040-NR[0].Page1[0].f1_39[0]"] == "5000.0"

    def test_prior_year_resident_answer_does_not_check_green_card_box(self):
        """Regression guard for a wrong-field bug: state.residency.
        prior_year_residency_status used to be written into c1_3[0], which
        is actually the real form's "were you ever a green card holder?"
        checkbox (Item D2) — a completely different, false disclosure.
        There is no field for "prior year resident" on the current
        revision, so it must stay unmapped (both D2 boxes blank)."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nro.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Ming"
        state.identity.last_name = "Chen"
        state.residency.prior_year_residency_status = "resident_alien"
        state.forms_required = []
        state.ready_for_assembly = True

        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        oi_path = next(p for p in generated if p.endswith("Schedule-OI.pdf"))
        fields = PdfReader(oi_path).get_fields() or {}
        assert fields["form1040-NR[0].Page1[0].c1_3[0]"].get("/V") == "/Off"
        assert fields["form1040-NR[0].Page1[0].c1_3[1]"].get("/V") == "/Off"


class TestFormPopulator8843VendoredTemplate:
    """End-to-end check that the real Form 8843 AcroForm PDF is filled
    correctly against the real field structure (dumped from the widget
    annotations' /AP/N export states, cross-checked against the printed
    line text) — regression guard for a rigorous audit that found: Part II
    (Teachers and Trainees) was never populated at all because routing
    ignored ``visa_subtype`` and defaulted every J-1 filer to Part III;
    the "first name and initial"/"last name" fields (f1_04/f1_05) were
    collapsed into one combined-name field, leaving f1_05 blank; Line 1a
    (f1_09, "type of visa and date you entered the US") was entirely
    unmapped; and every Yes/No line only ever mapped the "Yes" checkbox
    kid, so a computed "No" answer left both boxes blank instead of
    checking "No"."""

    def _templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"

    def _build_student_state(self) -> ReturnStateObject:
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Priya"
        state.identity.middle_initial = "R"
        state.identity.last_name = "Sharma"
        state.identity.itin = "912345678"
        state.identity.us_address_line1 = "123 Beacon St"
        state.identity.us_city = "Boston"
        state.identity.us_state = "MA"
        state.identity.us_zip = "02115"
        state.identity.foreign_address_line1 = "45 MG Road"
        state.identity.foreign_city = "Mumbai"
        state.identity.foreign_country = "IN"
        state.identity.country_of_citizenship = "IN"
        state.identity.passport_number = "N1234567"
        state.identity.passport_country = "IN"

        state.residency.exempt_visa_type = "F-1"
        state.residency.visa_subtype = "student"
        state.residency.first_us_entry_date = "2023-08-15"
        state.residency.years_in_exempt_status = 2
        state.residency.spt_days_current_year = 0
        state.residency.days_present_current_year = 300
        state.residency.days_present_year_minus_1 = 200
        state.residency.days_present_year_minus_2 = 10
        state.residency.is_exempt_individual = True
        state.residency.status = "nonresident_alien"

        state.forms_required = []
        state.ready_for_assembly = True
        return state

    def _build_teacher_state(self) -> ReturnStateObject:
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Wen"
        state.identity.last_name = "Li"
        state.identity.itin = "923456789"

        state.residency.exempt_visa_type = "J-1"
        state.residency.visa_subtype = "teacher_researcher"
        state.residency.first_us_entry_date = "2024-01-10"
        state.residency.years_in_exempt_status = 2
        state.residency.spt_days_current_year = 0
        state.residency.days_present_current_year = 355
        state.residency.days_present_year_minus_1 = 360
        state.residency.is_exempt_individual = True
        state.residency.status = "nonresident_alien"

        state.forms_required = []
        state.ready_for_assembly = True
        return state

    def _generate(self, state: ReturnStateObject) -> dict:
        repo_templates = self._templates_dir()
        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        pdf_path = next(p for p in generated if p.endswith("8843.pdf"))
        fields = PdfReader(pdf_path).get_fields() or {}
        return {k: v.get("/V") for k, v in fields.items()}

    def test_part_iii_student_fills_part_iii_not_part_ii(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f8843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        values = self._generate(self._build_student_state())
        P = "topmostSubform[0].Page1[0]."
        assert values[f"{P}f1_04[0]"] == "Priya R"
        assert values[f"{P}f1_05[0]"] == "Sharma"
        assert values[f"{P}f1_06[0]"] == "912345678"
        assert values[f"{P}f1_09[0]"] == "F-1, entered 08/15/2023"
        assert values[f"{P}f1_10[0]"] == "F-1"
        assert values[f"{P}f1_14[0]"] == "300"
        assert values[f"{P}f1_15[0]"] == "200"
        assert values[f"{P}f1_16[0]"] == "10"
        # first exempt year 2024 (2025 - years_in_exempt_status(2) + 1) ->
        # only the yr_minus_1 slot (f1_33) in Part III's line-11 grid fills.
        assert values[f"{P}f1_33[0]"] == "F-1"
        assert values[f"{P}f1_28[0]"] == ""
        # Part II's parallel line-7 grid (f1_20..f1_25) must stay untouched.
        assert values[f"{P}f1_25[0]"] == ""
        # Line 12 "No" (years_in_exempt_status=2, not >5) and line 13 "No"
        # (no LPR steps) must both resolve to their real checked states.
        assert values[f"{P}c1_2[0]"] == "/Off"
        assert values[f"{P}c1_2[1]"] == "/2"
        assert values[f"{P}c1_3[0]"] == "/Off"
        assert values[f"{P}c1_3[1]"] == "/2"
        # Part II's line-8 checkbox pair must stay untouched (not relevant).
        assert values[f"{P}c1_1[0]"] == "/Off"
        assert values[f"{P}c1_1[1]"] == "/Off"

    def test_part_ii_j1_teacher_researcher_fills_part_ii_not_part_iii(self):
        """Regression guard: a J-1 teacher/researcher (visa_subtype=
        'teacher_researcher') must land on Part II (lines 5-8), never
        Part III -- the pre-fix code ignored visa_subtype and routed every
        J-1 filer to Part III, silently dropping Part II entirely."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f8843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        values = self._generate(self._build_teacher_state())
        P = "topmostSubform[0].Page1[0]."
        assert values[f"{P}f1_10[0]"] == "J-1"
        # first exempt year 2024 -> only yr_minus_1 slot (f1_25) fills.
        assert values[f"{P}f1_25[0]"] == "J-1"
        assert values[f"{P}f1_20[0]"] == ""
        # Line 8 "No" (years_in_exempt_status=2, not >2).
        assert values[f"{P}c1_1[0]"] == "/Off"
        assert values[f"{P}c1_1[1]"] == "/2"
        # Part III must be entirely untouched for a Part II filer.
        assert values[f"{P}f1_33[0]"] == ""
        assert values[f"{P}c1_2[0]"] == "/Off"
        assert values[f"{P}c1_2[1]"] == "/Off"
        assert values[f"{P}c1_3[0]"] == "/Off"
        assert values[f"{P}c1_3[1]"] == "/Off"

    def test_line_12_yes_checks_real_yes_state_when_exempt_over_5_years(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f8843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_student_state()
        state.residency.years_in_exempt_status = 6
        values = self._generate(state)
        P = "topmostSubform[0].Page1[0]."
        assert values[f"{P}c1_2[0]"] == "/1"
        assert values[f"{P}c1_2[1]"] == "/Off"

    def test_part_iv_and_part_v_are_never_fabricated(self):
        """No intake path collects athlete/medical-condition data anywhere
        in ReturnStateObject; page 2's f2_01..f2_08 must stay unfilled."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f8843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        values = self._generate(self._build_student_state())
        for n in range(1, 9):
            key = f"topmostSubform[0].Page2[0].f2_{n:02d}[0]"
            assert values.get(key) in (None, ""), f"{key} should be blank"


class TestFormPopulatorScheduleNECVendoredTemplate:
    """End-to-end check that the real Schedule NEC AcroForm PDF is filled
    with correct, internally-consistent values against the real field
    structure (dumped and cross-checked against the printed "Nature of
    Income" table — see schedule_nec.py's module docstring). Guards
    several confirmed bugs found during a rigorous field-by-field audit:
    the header name/identifying number were never written at all, line 14
    ("multiply line 13 by rate of tax") was populated with a repeat of the
    line 13 income figure instead of the actual tax, line 13's 30% column
    was never wired up even though line 12's was, and the dollar amount
    used gross pre-treaty FDAP instead of the net (post-treaty) amount
    consistent with the actual tax liability."""

    def _templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"

    def _build_state(self) -> ReturnStateObject:
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Ming"
        state.identity.middle_initial = "Q"
        state.identity.last_name = "Chen"
        state.identity.itin = "912345678"
        state.identity.filing_status = "single"
        state.residency.exempt_visa_type = "F-1"
        state.forms_required = []
        state.ready_for_assembly = True
        return state

    def _generate_nec(self, state: ReturnStateObject) -> dict:
        repo_templates = self._templates_dir()
        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        nec_path = next(p for p in generated if p.endswith("Schedule-NEC.pdf"))
        fields = PdfReader(nec_path).get_fields() or {}
        return {k: v.get("/V") for k, v in fields.items()}

    def test_fjmq_scholarship_fills_other_rate_column_with_real_tax_not_income(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nrn.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.income.fdap_taxable_total = 5000.0
        state.tax.fdap_tax_liability = 700.0  # 5000 * 14%
        values = self._generate_nec(state)

        prefix = "form1040-NR[0].Page1[0]"
        # Header — every attached schedule must repeat name + identifying number.
        assert values[f"{prefix}.f1_1[0]"] == "Ming Q Chen"
        assert values[f"{prefix}.f1_2[0]"] == "912345678"
        # (d) column's rate blank carries the 14% §1441(b) rate actually used.
        assert values[f"{prefix}.Table_NatureOfIncome[0].Header[0].f1_3[0]"] == "14"
        # The second "Other" sub-column has no corresponding data bucket in
        # this engine and is intentionally never mapped/written at all.
        assert values[f"{prefix}.Table_NatureOfIncome[0].Header[0].f1_4[0]"] is None
        # Line 12 (income) and line 13 (subtotal) both show the $5,000 amount...
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line12[0].f1_87[0]"] == "5000"
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line13[0].f1_92[0]"] == "5000"
        # ...but line 14 ("multiply line 13 by rate of tax") must be the
        # actual $700 tax, not another copy of the $5,000 income figure.
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line14[0].f1_97[0]"] == "700"
        # Line 15 must match line 14 exactly (single-column case) and is
        # what form_1040nr.py also writes to 1040-NR line 23a.
        assert values[f"{prefix}.f1_99[0]"] == "700"
        # Untouched columns/rows stay genuinely blank (never "0").
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line1a[0].f1_7[0]"] == ""
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line11[0].f1_79[0]"] == ""

    def test_non_fjmq_visa_fills_30_percent_column_including_line_13(self):
        """Regression guard: line 13's 30% box (f1_91) was never mapped at
        all before this fix, so a non-F/J/M/Q filer's Schedule NEC would
        show a dollar amount on line 12 with no matching line 13 subtotal."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nrn.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.residency.exempt_visa_type = None
        state.income.fdap_taxable_total = 1500.0
        state.tax.fdap_tax_liability = 450.0  # 1500 * 30%
        values = self._generate_nec(state)

        prefix = "form1040-NR[0].Page1[0]"
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line12[0].f1_86[0]"] == "1500"
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line13[0].f1_91[0]"] == "1500"
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line14[0].f1_96[0]"] == "450"
        assert values[f"{prefix}.f1_99[0]"] == "450"
        # No custom rate needed for the statutory 30% column — the rate
        # blank is explicitly cleared (empty string), not left untouched.
        assert values[f"{prefix}.Table_NatureOfIncome[0].Header[0].f1_3[0]"] == ""

    def test_partial_treaty_exemption_reports_net_fdap_on_real_pdf(self):
        """$8,000 gross scholarship with a $5,000 China Art 20(b) treaty
        exemption must show the $3,000 NET amount on lines 12/13, not the
        $8,000 gross IncomeState total — regression guard for a confirmed
        gross-vs-net mismatch bug."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nrn.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.income.fdap_taxable_total = 8000.0
        state.treaty.applied_benefits = [
            {
                "country_iso2": "CN", "country_name": "China (People's Republic of)",
                "article_id": "20(b)", "category": "scholarship_fellowship",
                "exempt_amount": 5000.0, "requires_form_8833": False,
                "explanation": "US-China treaty Article 20(b) scholarship exemption.",
            }
        ]
        state.tax.fdap_tax_liability = 420.0  # (8000 - 5000) * 14%
        values = self._generate_nec(state)

        prefix = "form1040-NR[0].Page1[0]"
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line12[0].f1_87[0]"] == "3000"
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line13[0].f1_92[0]"] == "3000"
        assert values[f"{prefix}.Table_NatureOfIncome[0].Line14[0].f1_97[0]"] == "420"
        assert values[f"{prefix}.f1_99[0]"] == "420"


class TestFormPopulatorScheduleAVendoredTemplate:
    """End-to-end check that the real Schedule A (Form 1040-NR) AcroForm PDF
    is filled with correct, internally-consistent values against the real
    field structure — dumped via widget-annotation /Parent-chain walking and
    cross-checked against the printed line text via a position-sorted text
    extraction (see schedule_a.py's module docstring). Guards several
    confirmed bugs found during a rigorous field-by-field audit: the header
    name/identifying number were never written at all, line 1a showed the
    already-SALT-capped amount instead of the raw pre-cap figure, and line
    1b (a numeric AcroForm field) held a free-text warning sentence instead
    of the actual capped dollar amount."""

    def _templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"

    def _build_state(self) -> ReturnStateObject:
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Priya"
        state.identity.middle_initial = "R"
        state.identity.last_name = "Sharma"
        state.identity.itin = "987654321"
        state.identity.filing_status = "single"
        state.forms_required = []
        state.ready_for_assembly = True
        return state

    def _generate_sch_a(self, state: ReturnStateObject) -> dict:
        repo_templates = self._templates_dir()
        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        sch_a_path = next(p for p in generated if p.endswith("Schedule-A.pdf"))
        fields = PdfReader(sch_a_path).get_fields() or {}
        return {k: v.get("/V") for k, v in fields.items()}

    def test_full_line_by_line_consistency_with_salt_cap_bite(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nra.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.sch_a = {
            "state_local_income_tax": 40000.0,  # capped (line 1b)
            "salt_cap_bite": 8000.0,            # raw was 48,000
            "charitable_cash": 1200.0,
            "charitable_noncash": 300.0,
            "casualty_disaster_loss": 2500.0,
            "other_itemized": 150.0,
            "total": 44150.0,
            "disallowed_items": [
                "Mortgage interest ($12,000) is not deductible on Form 1040-NR Schedule A.",
            ],
        }
        values = self._generate_sch_a(state)

        prefix = "form1040-NR[0].Page1[0]"
        # Header — every attached schedule must repeat name + identifying number.
        assert values[f"{prefix}.f1_1[0]"] == "Priya R Sharma"
        assert values[f"{prefix}.f1_2[0]"] == "987654321"
        # Line 1a: raw pre-cap total (confirmed-broken bug: used to show the
        # already-capped amount here instead).
        assert values[f"{prefix}.Line1a_ReadOrder[0].f1_3[0]"] == "48000"
        # Line 1b: the capped amount (confirmed-broken bug: used to hold a
        # free-text warning sentence here instead of a number).
        assert values[f"{prefix}.f1_4[0]"] == "40000"
        # Lines 2-6.
        assert values[f"{prefix}.Line2_ReadOrder[0].f1_5[0]"] == "1200"
        assert values[f"{prefix}.f1_6[0]"] == "300"
        assert values[f"{prefix}.f1_7[0]"] == ""  # line 4 carryover — no state field exists
        assert values[f"{prefix}.f1_8[0]"] == "1500"  # line 5 = 1200 + 300 + 0
        assert values[f"{prefix}.f1_9[0]"] == "2500"  # line 6 casualty
        # Line 7 — dollar amount only; the free-text "type" box has no
        # backing state field and must stay genuinely unmapped.
        assert values[f"{prefix}.f1_11[0]"] == "150"
        assert values[f"{prefix}.Line7Entry[0].f1_10[0]"] is None
        # Line 8 total = 1b(40000) + 5(1500) + 6(2500) + 7(150) = 44150.
        assert values[f"{prefix}.f1_12[0]"] == "44150"

    def test_no_salt_cap_bite_line_1a_equals_line_1b(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nra.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.sch_a = {
            "state_local_income_tax": 3000.0,
            "salt_cap_bite": 0.0,
            "charitable_cash": 500.0,
            "total": 3500.0,
        }
        values = self._generate_sch_a(state)

        prefix = "form1040-NR[0].Page1[0]"
        assert values[f"{prefix}.Line1a_ReadOrder[0].f1_3[0]"] == "3000"
        assert values[f"{prefix}.f1_4[0]"] == "3000"
        assert values[f"{prefix}.f1_12[0]"] == "3500"

    def test_mfs_salt_cap_flows_through_real_pdf(self):
        """End-to-end regression guard for the stale $10,000 flat SALT cap
        bug: compute_sch_a_nra's real TY2025 filing-status-aware cap
        ($20,000 MFS / $40,000 single) must reach the actual PDF fields,
        not just the in-memory SchAResult."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f1040nra.pdf").exists():
            pytest.skip("IRS templates not vendored")

        from src.functions.sch_a_nra import compute_sch_a_nra

        result = compute_sch_a_nra(
            filing_status="mfs",
            state_income_tax_withheld=15000,
            local_income_tax_withheld=10000,  # raw 25,000 > $20,000 MFS cap
        )
        state = self._build_state()
        state.identity.filing_status = "mfs"
        state.sch_a = result.to_dict_floats()
        values = self._generate_sch_a(state)

        prefix = "form1040-NR[0].Page1[0]"
        assert values[f"{prefix}.Line1a_ReadOrder[0].f1_3[0]"] == "25000"
        assert values[f"{prefix}.f1_4[0]"] == "20000"
        assert values[f"{prefix}.f1_12[0]"] == "20000"


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

        def _line6_field_num(key: str) -> int | None:
            leaf = key.rsplit(".", 1)[-1]  # e.g. "f1_14[0]"
            if not leaf.startswith("f1_"):
                return None
            digits = leaf[len("f1_"):].split("[", 1)[0]
            try:
                n = int(digits)
            except ValueError:
                return None
            return n if 12 <= n <= 36 else None

        def _explanation_text(vals: dict) -> str:
            # Line 6 (f1_12..f1_36) is a run of single-line text fields the
            # populator word-wraps a single narrative across — reassemble it
            # in field order to check content, since no one field holds the
            # whole sentence.
            numbered = sorted(
                ((_line6_field_num(k), k) for k in vals if _line6_field_num(k) is not None),
            )
            return " ".join(str(vals[k]) for _, k in numbered)

        values_1 = _real_values(pdfs_8833[0])
        values_2 = _real_values(pdfs_8833[1])

        all_articles_seen = set()
        for vals in (values_1, values_2):
            all_articles_seen.update(v for v in vals.values() if v in ("20(c)", "20(b)"))
        assert all_articles_seen == {"20(c)", "20(b)"}, (
            "each row's own article must land in its own PDF, not be shared/"
            f"cross-contaminated — saw {all_articles_seen}"
        )

        # Form 8833 has no standalone "amount exempted" field — real Line 6
        # instructions require the dollar amount to be part of the written
        # explanation. Confirm each row's own amount lands in its own PDF's
        # explanation text, and the other row's amount does NOT leak in.
        text_1 = _explanation_text(values_1)
        text_2 = _explanation_text(values_2)
        assert "$5,000" in text_1 and "$3,000" not in text_1
        assert "$3,000" in text_2 and "$5,000" not in text_2


class TestFormPopulator8316VendoredTemplate:
    """End-to-end check that the real Form 8316 AcroForm PDF is filled
    correctly against the real widget structure (dumped from the widget
    annotations' /AP/N export states, cross-checked against the printed
    line text): fields 'A', '1', '3', '7' are Yes/No radio groups with real
    export states /1=Yes, /2=No; field '5' is a Yes/No/Do-not-Know radio
    group with a real third state /3 that a bool-plus-/_States_-fallback
    (which defaults to '/1') would never reach."""

    def _templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"

    def _build_state(self) -> ReturnStateObject:
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Ming"
        state.identity.last_name = "Chen"
        state.identity.itin = "912345678"
        state.identity.daytime_phone = "617-555-0199"

        state.residency.status = "nonresident_alien"
        state.residency.exempt_visa_type = "F-1"
        state.residency.is_exempt_individual = True

        state.income.employer_name = "Boston University"
        state.income.employer_ein = "04-1234567"
        state.income.raw_ss_withheld = 1860.0
        state.income.raw_medicare_withheld = 435.0

        state.fica.is_exempt = True
        state.fica.incorrect_ss_withheld = 1860.0
        state.fica.incorrect_medicare_withheld = 435.0
        state.fica.requires_form_843 = True
        state.fica.employer_attempted_refund = True
        state.fica.has_form_8316 = False

        state.forms_required = ["843", "8316"]
        state.ready_for_assembly = True
        return state

    def _generate(self, state: ReturnStateObject) -> str:
        repo_templates = self._templates_dir()
        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        return next(p for p in generated if p.endswith("8316.pdf"))

    def _widget_export_states(self, pdf_path: str) -> dict:
        """Map fully-qualified field name -> {kid export state: /AS value}
        by walking the raw widget annotations, the same way the real
        checkbox-resolution audit does — reader.get_fields()'s aggregated
        /_States_/'/V' is not enough to confirm *which* radio kid actually
        rendered as checked."""
        reader = PdfReader(pdf_path)
        page = reader.pages[0]
        result: dict = {}
        for annot in page["/Annots"]:
            obj = annot.get_object()
            if obj.get("/Subtype") != "/Widget":
                continue
            name_parts = []
            cur = obj
            while cur is not None:
                t = cur.get("/T")
                if t:
                    name_parts.insert(0, str(t))
                parent = cur.get("/Parent")
                cur = parent.get_object() if parent is not None else None
            fqname = ".".join(name_parts)
            ap = obj.get("/AP")
            states = list(ap["/N"].keys()) if ap and "/N" in ap else []
            result.setdefault(fqname, {})
            for s in states:
                result[fqname][s] = str(obj.get("/AS"))
        return result

    def test_yes_no_and_do_not_know_radios_resolve_real_states(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f8316.pdf").exists():
            pytest.skip("IRS templates not vendored")

        pdf_path = self._generate(self._build_state())
        widgets = self._widget_export_states(pdf_path)

        # Line A: Yes (/1) is checked, No (/2) kid stays /Off.
        assert widgets["A"] == {"/1": "/1", "/2": "/Off"}
        # Lines 1, 3, 7: No (/2) is checked, Yes (/1) kid stays /Off.
        for line in ("1", "3", "7"):
            assert widgets[line] == {"/1": "/Off", "/2": "/2"}, line
        # Line 5 has a real third state -- Do not Know (/3) is checked,
        # both Yes (/1) and No (/2) kids stay /Off. This is the state a
        # bool-plus-/_States_-fallback would never reach (it only ever
        # resolves to the first non-/Off state, "/1").
        assert widgets["5"] == {"/1": "/Off", "/2": "/Off", "/3": "/3"}

        fields = PdfReader(pdf_path).get_fields() or {}
        values = {k: v.get("/V") for k, v in fields.items()}
        assert values["A"] == "/1"
        assert values["1"] == "/2"
        assert values["3"] == "/2"
        assert values["5"] == "/3"
        assert values["7"] == "/2"

    def test_amount_lines_stay_blank_and_employer_phone_flow_through(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f8316.pdf").exists():
            pytest.skip("IRS templates not vendored")

        pdf_path = self._generate(self._build_state())
        fields = PdfReader(pdf_path).get_fields() or {}
        values = {k: v.get("/V") for k, v in fields.items()}

        # Every "if yes, show amount" line stays blank since every
        # underlying question is answered No/Do Not Know, not Yes.
        for key in ("FillText01", "FillText03", "FillText05", "FillText10"):
            assert values.get(key) in (None, ""), f"{key} should be blank"

        assert values["FillText7"] == "Boston University"
        assert values["FillText12"] == "617-555-0199"
        # No intake field captures "convenient hours to call" anywhere in
        # ReturnStateObject; FillText11 must stay genuinely unfilled, not
        # fabricated.
        assert values.get("FillText11") in (None, "")


class TestFormPopulator843VendoredTemplate:
    """End-to-end check that the real Form 843 AcroForm PDF is filled
    correctly against the real field structure (dumped from the widget
    annotations' /AP/N export states, cross-checked against the printed
    line text via position-sorted extract_text) — regression guard for a
    rigorous audit that found: the "type of tax" text ("FICA") was written
    into f1_1[0], which is actually the free-text "specify" box for line
    1 item q ("Other (specify)"), completely unrelated to the FICA claim
    and with no corresponding checkbox ever checked; line 1's actual
    reason checkbox (item e, c1_1[4]) was never checked at all; line 4's
    "type of tax" checkbox (a Employment, c1_2[0]) was never checked; line
    5's "type of return" checkbox (d 941, c2_4[0]) was never checked; the
    employer's NAME was written into f1_15[0] ("Name and address shown on
    return if different from above" — a taxpayer-identity field, not an
    employer field, and one for which this engine never has real data
    since it always uses one consistent identity); and the city/state/ZIP
    address block (f1_8/f1_9/f1_10, three separate boxes) was collapsed
    into a single combined string crammed entirely into the city box."""

    def _templates_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "templates" / "2025"

    def _build_state(self) -> ReturnStateObject:
        state = ReturnStateObject(tax_year=2025)
        state.identity.first_name = "Priya"
        state.identity.middle_initial = "R"
        state.identity.last_name = "Sharma"
        state.identity.itin = "912345678"
        state.identity.us_address_line1 = "123 Beacon St"
        state.identity.us_address_line2 = "Apt 4B"
        state.identity.us_city = "Boston"
        state.identity.us_state = "MA"
        state.identity.us_zip = "02115"
        state.identity.daytime_phone = "617-555-1234"
        state.identity.foreign_country = "IN"
        state.identity.foreign_state_province = "Maharashtra"
        state.identity.foreign_postal_code = "400001"
        state.identity.foreign_address_line1 = "45 MG Road"
        state.identity.foreign_city = "Mumbai"

        state.residency.status = "nonresident_alien"
        state.residency.exempt_visa_type = "F-1"
        state.residency.is_exempt_individual = True

        state.income.employer_name = "Acme University"
        state.income.employer_ein = "12-3456789"
        state.income.raw_ss_withheld = 1860.0
        state.income.raw_medicare_withheld = 435.0

        state.fica.is_exempt = True
        state.fica.incorrect_ss_withheld = 1860.0
        state.fica.incorrect_medicare_withheld = 435.0
        state.fica.requires_form_843 = True
        state.fica.employer_attempted_refund = True
        state.fica.has_form_8316 = True

        state.forms_required = ["843"]
        state.ready_for_assembly = True
        return state

    def _generate(self, state: ReturnStateObject) -> dict:
        repo_templates = self._templates_dir()
        out = tempfile.mkdtemp()
        populator = FormPopulator(
            templates_dir=str(repo_templates.parent), outputs_dir=out, tax_year=2025,
        )
        generated = populator.generate_filing_package(state)
        # NOTE: "843".pdf must NOT match Form 8843's output — endswith
        # "843.pdf" would incorrectly match "..._8843.pdf" too.
        pdf_path = next(p for p in generated if p.endswith("_843.pdf"))
        fields = PdfReader(pdf_path).get_fields() or {}
        return {k: v.get("/V") for k, v in fields.items()}

    def test_identity_and_address_fields(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        values = self._generate(self._build_state())
        P = "topmostSubform[0].Page1[0]."
        assert values[f"{P}f1_2[0]"] == "Priya R Sharma"
        assert values[f"{P}f1_3[0]"] == "912345678"
        assert values[f"{P}f1_6[0]"] == "123 Beacon St"
        assert values[f"{P}f1_7[0]"] == "Apt 4B"
        # City/State/ZIP are three SEPARATE boxes, not one combined string.
        assert values[f"{P}f1_8[0]"] == "Boston"
        assert values[f"{P}f1_9[0]"] == "MA"
        assert values[f"{P}f1_10[0]"] == "02115"
        assert values[f"{P}f1_11[0]"] == "12-3456789"
        assert values[f"{P}f1_16[0]"] == "617-555-1234"
        # No foreign address in play (US address present) -> foreign boxes
        # and the "name/address if different from return" box stay blank.
        assert values.get(f"{P}f1_12[0]") in (None, "")
        assert values.get(f"{P}f1_13[0]") in (None, "")
        assert values.get(f"{P}f1_14[0]") in (None, "")
        assert values.get(f"{P}f1_15[0]") in (None, "")
        # The employer's name/EIN must never land in the taxpayer-identity
        # "different from return" box -- only the dedicated EIN box.
        assert "Acme" not in (values.get(f"{P}f1_15[0]") or "")

    def test_foreign_address_used_when_no_us_address_on_file(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        state = self._build_state()
        state.identity.us_address_line1 = ""
        state.identity.us_address_line2 = ""
        state.identity.us_city = ""
        state.identity.us_state = ""
        state.identity.us_zip = ""
        values = self._generate(state)
        P = "topmostSubform[0].Page1[0]."
        assert values[f"{P}f1_6[0]"] == "45 MG Road"
        assert values[f"{P}f1_8[0]"] == "Mumbai"
        # Domestic state/ZIP boxes don't apply to a foreign address.
        assert values.get(f"{P}f1_9[0]") in (None, "")
        assert values.get(f"{P}f1_10[0]") in (None, "")
        assert values[f"{P}f1_12[0]"] == "IN"
        assert values[f"{P}f1_13[0]"] == "Maharashtra"
        assert values[f"{P}f1_14[0]"] == "400001"

    def test_reason_and_type_of_tax_checkboxes_are_checked_to_real_states(self):
        """Line 1 item e, line 4 item a (Employment), and line 5 item d
        (Form 941) must all resolve to their real checked export states --
        never left /Off and never a wrong fallback state."""
        repo_templates = self._templates_dir()
        if not (repo_templates / "f843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        values = self._generate(self._build_state())
        P1 = "topmostSubform[0].Page1[0]."
        P2 = "topmostSubform[0].Page2[0]."
        # Line 1 item e ("withheld in error") -- real export state /5.
        assert values[f"{P1}c1_1[4]"] == "/5"
        # No sibling reason box is spuriously checked, e.g. item c
        # ("excess" withholding, a different fact pattern) stays /Off.
        assert values[f"{P1}c1_1[2]"] == "/Off"
        # Line 4 item a (Employment tax) -- real export state /1.
        assert values[f"{P1}c1_2[0]"] == "/1"
        for kid in ("c1_3[0]", "c1_4[0]", "c1_5[0]", "c1_6[0]", "c1_7[0]", "c1_8[0]"):
            assert values[f"{P1}{kid}"] == "/Off"
        # Line 5 item d (Form 941) -- real export state /1.
        assert values[f"{P2}c2_4[0]"] == "/1"
        for kid in (
            "c2_1[0]", "c2_2[0]", "c2_3[0]", "c2_5[0]", "c2_6[0]", "c2_7[0]",
            "c2_8[0]", "c2_9[0]", "c2_10[0]", "c2_11[0]", "c2_12[0]", "c2_13[0]", "c2_14[0]",
        ):
            assert values[f"{P2}{kid}"] == "/Off"
        # Line 7 (penalty/interest abatement reason) never applies to a
        # FICA refund claim -- must stay entirely unchecked.
        for kid in ("c2_15[0]", "c2_15[1]", "c2_15[2]", "c2_15[3]"):
            assert values[f"{P2}{kid}"] == "/Off"
        # f1_1[0] is the "Other (specify)" free-text line for item q, not a
        # general "type of tax" box -- must stay blank since item q is
        # never checked.
        assert values.get(f"{P1}f1_1[0]") in (None, "")

    def test_amount_and_explanation_text(self):
        repo_templates = self._templates_dir()
        if not (repo_templates / "f843.pdf").exists():
            pytest.skip("IRS templates not vendored")

        values = self._generate(self._build_state())
        P1 = "topmostSubform[0].Page1[0]."
        P2 = "topmostSubform[0].Page2[0]."
        assert values[f"{P1}f1_17[0]"] == "01-01-2025"
        assert values[f"{P1}f1_18[0]"] == "12-31-2025"
        # Whole-dollar formatted (no trailing ".0"), matching every other
        # form populator's money-field convention.
        assert values[f"{P1}f1_19[0]"] == "2295"
        assert values[f"{P2}f2_2[0]"] == "IRC §3121(b)(19)"
        text = values[f"{P2}ExplainWhy[0].f2_3[0]"]
        assert "confirmed in writing that it will not issue a refund" in text
        # Line 3's 12 per-payment-date boxes have no backing per-paycheck
        # data anywhere in state (only annual W-2 totals) -- must stay
        # genuinely blank rather than fabricated.
        for n in range(20, 32):
            key = f"{P1}f1_{n}[0]"
            assert values.get(key) in (None, ""), f"{key} should be blank"
