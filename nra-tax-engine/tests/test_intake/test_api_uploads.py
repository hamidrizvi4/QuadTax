"""Tests for the FastAPI endpoints (Phase 6 typed payload)."""

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
            "OcrResult",
            "W2Extracted",
            "I94Extracted",
            "Form1042SExtracted",
            "Form1099Extracted",
        ):
            assert name in schemas, f"Missing schema: {name}"

    def test_openapi_includes_ocr_and_packet_paths(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        paths = r.json()["paths"]
        assert "/api/v1/ocr" in paths
        assert "/api/v1/packet" in paths


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
        r = client.post(
            "/api/v1/submit",
            json=payload,
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
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
        r = client.post(
            "/api/v1/submit",
            json=payload,
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 422

    @patch("src.api.main.TaxEngine.run_full_pipeline")
    def test_submit_surfaces_human_review_reasons_not_opaque_500(self, mock_run):
        """A HumanReviewRequiredError (e.g. a §6013 election or large foreign
        gift the engine can't handle) must reach the caller as an actionable
        422 with the reasons, not the generic opaque 500 every other
        pipeline failure gets."""
        from src.orchestrator.engine import HumanReviewRequiredError

        mock_run.side_effect = HumanReviewRequiredError(
            ["Elections: filer received gifts/bequests over $100,000 ... Form 3520 ..."]
        )

        payload = {
            "intake": {
                "identity": {
                    "first_name": "Wei",
                    "last_name": "Chen",
                    "itin": "912345678",
                    "filing_status": "single",
                },
                "residency": {"tax_year": 2025, "visa_type": "F-1", "first_us_arrival_year": 2024},
                "income": {
                    "income_description": "TA",
                    "requires_services": True,
                    "is_qualified_expense": False,
                },
                "elections": {"large_foreign_gifts_over_100k": True},
            },
            "i94_ocr_text": "i94",
            "w2_ocr_texts": ["w2"],
            "form_1042s_ocr_texts": [],
        }
        r = client.post(
            "/api/v1/submit",
            json=payload,
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 422, r.text
        body = r.json()["detail"]
        assert body["error"] == "human_review_required"
        assert any("Form 3520" in reason for reason in body["reasons"])


class TestOcrEndpoint:
    """POST /api/v1/ocr — extracts structured fields from uploaded documents."""

    @patch("src.api.ocr_endpoint.DocumentExtractor.__init__", return_value=None)
    @patch("src.api.ocr_endpoint.DocumentExtractor.extract_all")
    def test_ocr_endpoint_happy_path(self, mock_extract_all, _mock_init):
        from src.intake.document_extractor import (
            I94Extracted,
            OcrResult,
            W2Extracted,
        )

        mock_extract_all.return_value = OcrResult(
            i94=I94Extracted(days_current_year=330, latest_class_of_admission="F-1"),
            w2s=[W2Extracted(box_1_wages=32500.0, employer_name="NYU")],
        )

        r = client.post(
            "/api/v1/ocr",
            data={"tax_year": "2025"},
            files={
                "i94_file": ("i94.pdf", b"i94-bytes", "application/pdf"),
                "w2_files": ("w2.pdf", b"w2-bytes", "application/pdf"),
            },
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["i94"]["days_current_year"] == 330
        assert body["w2s"][0]["box_1_wages"] == 32500.0
        mock_extract_all.assert_called_once()

    @patch("src.api.ocr_endpoint.DocumentExtractor.__init__", return_value=None)
    @patch("src.api.ocr_endpoint.DocumentExtractor.extract_all")
    def test_ocr_endpoint_no_files_returns_empty_result(self, mock_extract_all, _mock_init):
        from src.intake.document_extractor import OcrResult

        mock_extract_all.return_value = OcrResult()
        r = client.post(
            "/api/v1/ocr",
            data={"tax_year": "2025"},
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["i94"] is None
        assert body["w2s"] == []

    @patch("src.api.ocr_endpoint.DocumentExtractor.__init__", return_value=None)
    @patch("src.api.ocr_endpoint.DocumentExtractor.extract_all")
    def test_ocr_endpoint_defaults_tax_year_to_2025(self, mock_extract_all, _mock_init):
        from src.intake.document_extractor import OcrResult

        mock_extract_all.return_value = OcrResult()
        r = client.post(
            "/api/v1/ocr",
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 200
        _, kwargs = mock_extract_all.call_args
        assert kwargs["tax_year"] == 2025

    @patch("src.api.ocr_endpoint.DocumentExtractor.__init__", return_value=None)
    @patch("src.api.ocr_endpoint.DocumentExtractor.extract_all")
    def test_ocr_endpoint_surfaces_extraction_failure_as_500(self, mock_extract_all, _mock_init):
        mock_extract_all.side_effect = RuntimeError("OCR backend unavailable")
        r = client.post(
            "/api/v1/ocr",
            files={"i94_file": ("i94.pdf", b"bytes", "application/pdf")},
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 500
        detail = r.json()["detail"]
        # The endpoint must not leak the underlying error message — it returns
        # an opaque, reference-tagged failure instead.
        assert detail.startswith("Internal extraction error")
        assert "OCR backend unavailable" not in detail

    @patch("src.api.ocr_endpoint.DocumentExtractor.__init__", return_value=None)
    @patch("src.api.ocr_endpoint.DocumentExtractor.extract_all")
    def test_ocr_endpoint_multiple_w2s_and_1042s(self, mock_extract_all, _mock_init):
        from src.intake.document_extractor import (
            Form1042SExtracted,
            OcrResult,
            W2Extracted,
        )

        mock_extract_all.return_value = OcrResult(
            w2s=[
                W2Extracted(box_1_wages=5000.0),
                W2Extracted(box_1_wages=8000.0),
            ],
            form_1042s=[Form1042SExtracted(income_code=16, gross_income=3000.0)],
        )
        r = client.post(
            "/api/v1/ocr",
            files=[
                ("w2_files", ("w2a.pdf", b"a", "application/pdf")),
                ("w2_files", ("w2b.pdf", b"b", "application/pdf")),
                ("form_1042s_files", ("1042s.pdf", b"c", "application/pdf")),
            ],
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["w2s"]) == 2
        assert len(body["form_1042s"]) == 1


class TestPacketEndpoint:
    """GET /api/v1/packet — serves a generated packet file, path-traversal guarded."""

    def test_packet_rejects_path_outside_outputs(self, tmp_path):
        r = client.get(
            "/api/v1/packet",
            params={"path": "/etc/passwd"},
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 403

    def test_packet_rejects_sibling_directory_lookalike(self, tmp_path, monkeypatch):
        """Regression: a naive ``str.startswith`` prefix check would let
        ``outputs_evil/`` pass because the string "outputs_evil" starts with
        "outputs". The endpoint must use a real path-containment check."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "outputs").mkdir()
        evil_dir = tmp_path / "outputs_evil"
        evil_dir.mkdir()
        evil_file = evil_dir / "secret.pdf"
        evil_file.write_bytes(b"%PDF-fake")

        r = client.get(
            "/api/v1/packet",
            params={"path": str(evil_file)},
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 403

    def test_packet_404_for_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "outputs").mkdir()
        r = client.get(
            "/api/v1/packet",
            params={"path": str(tmp_path / "outputs" / "does_not_exist.pdf")},
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 404

    def test_packet_serves_file_within_outputs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        packet_file = outputs_dir / "packet_federal.pdf"
        packet_file.write_bytes(b"%PDF-fake-packet-bytes")

        r = client.get(
            "/api/v1/packet",
            params={"path": str(packet_file)},
            headers={"Authorization": "Bearer test-key-not-a-secret"},
        )
        assert r.status_code == 200
        assert r.content == b"%PDF-fake-packet-bytes"
