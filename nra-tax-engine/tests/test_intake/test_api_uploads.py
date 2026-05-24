"""Tests for the FastAPI endpoints (Phase 6 typed payload + legacy multipart)."""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.orchestrator.state import ReturnStateObject

client = TestClient(app)


class TestHealthz:
    def test_healthz(self):
        r = client.get("/api/v1/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestOpenAPISchema:
    """The auto-generated spec must include every intake submodel."""

    def test_openapi_includes_intake_payload(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        schemas = r.json()["components"]["schemas"]
        for name in (
            "IntakePayload",
            "IntakeIdentity",
            "IntakeResidency",
            "IntakeIncome",
            "IntakeNYContext",
            "IntakeFICA",
            "IntakeBanking",
            "IntakeElections",
            "SubmitRequest",
            "TaxProcessResponse",
        ):
            assert name in schemas, f"Missing schema: {name}"


class TestSubmitEndpoint:
    """Modern typed endpoint."""

    @patch("src.api.main.MailingPackager.assemble")
    @patch("src.api.main.TaxEngine.run_full_pipeline")
    def test_submit_minimal_payload(self, mock_run, mock_assemble):
        dummy = ReturnStateObject(tax_year=2025)
        dummy.tax.total_tax_liability = 2762.0
        dummy.tax.refund_or_owed = -1738.0
        dummy.fica.requires_form_843 = True
        dummy.fica.incorrect_ss_withheld = 1860.0
        dummy.fica.incorrect_medicare_withheld = 435.0
        dummy.ny.ny_refund_or_owed = -155.0
        dummy.forms_required = ["8833", "843", "IT-203"]
        dummy.completed_layers = ["L1", "L3", "L4", "L6", "L7", "L8", "L9"]
        mock_run.return_value = (["outputs/student_1040-NR.fieldmap.json"], dummy)

        from src.assembly.mailing_packager import MailingPackage, PacketManifest

        mock_assemble.return_value = MailingPackage(
            federal=PacketManifest(name="federal", json_output="/tmp/p_federal.json"),
            ny=PacketManifest(name="ny", json_output="/tmp/p_ny.json"),
            fica_843=PacketManifest(name="fica_843", json_output="/tmp/p_843.json"),
        )

        payload = {
            "intake": {
                "identity": {
                    "first_name": "Ming",
                    "last_name": "Chen",
                    "itin": "912345678",
                    "country_of_tax_residence": "CN",
                    "filing_status": "single",
                },
                "residency": {
                    "tax_year": 2025,
                    "visa_type": "F-1",
                    "first_us_arrival_year": 2024,
                },
                "income": {
                    "income_description": "On-campus job",
                    "requires_services": True,
                    "is_qualified_expense": False,
                },
            },
            "i94_ocr_text": "i94",
            "w2_ocr_texts": ["w2"],
            "form_1042s_ocr_texts": [],
        }
        r = client.post("/api/v1/submit", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "success"
        assert body["tax_year"] == 2025
        assert body["federal_refund_or_owed"] == -1738.0
        assert body["ny_refund_or_owed"] == -155.0
        assert body["fica_refund_amount"] == 2295.0  # 1860 + 435
        assert "8833" in body["forms_required"]
        assert body["federal_packet_path"] == "/tmp/p_federal.json"
        assert body["ny_packet_path"] == "/tmp/p_ny.json"
        assert body["fica_packet_path"] == "/tmp/p_843.json"

    def test_submit_rejects_invalid_filing_status(self):
        payload = {
            "intake": {
                "identity": {"filing_status": "mfj"},  # invalid for NRA
                "residency": {},
                "income": {},
            }
        }
        r = client.post("/api/v1/submit", json=payload)
        assert r.status_code == 422


class TestLegacyUploadEndpoint:
    @patch("src.api.main.DocumentParser.parse_file")
    @patch("src.api.main.TaxEngine.run_full_pipeline")
    def test_legacy_multipart_path(self, mock_run, mock_parse):
        mock_parse.return_value = "DUMMY OCR"
        dummy = ReturnStateObject(tax_year=2025)
        dummy.tax.total_tax_liability = 2000.0
        dummy.tax.refund_or_owed = -500.0
        dummy.fica.requires_form_843 = True
        dummy.fica.incorrect_ss_withheld = 1000.0
        dummy.fica.incorrect_medicare_withheld = 250.0
        dummy.forms_required = ["8833"]
        mock_run.return_value = (["outputs/x.json"], dummy)

        mcq = {
            "tax_year": 2025,
            "visa_type": "F-1",
            "first_us_arrival_year": 2024,
            "tax_residence_country": "China",
            "income_description": "TA",
            "requires_services": True,
            "is_qualified_expense": False,
        }
        r = client.post(
            "/api/v1/upload-and-process",
            data={"mcq_answers_json": json.dumps(mcq)},
            files={
                "i94_file": ("i94.pdf", b"x", "application/pdf"),
                "w2_files": ("w2.pdf", b"y", "application/pdf"),
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["federal_refund_or_owed"] == -500.0
        assert body["fica_refund_amount"] == 1250.0
        assert body["forms_required"] == ["8833"]
