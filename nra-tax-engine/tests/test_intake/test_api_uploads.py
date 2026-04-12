"""Tests for the API multipart upload endpoints."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.orchestrator.state import ReturnStateObject

client = TestClient(app)


class TestApiUploads:
    """Validate that the FastAPI endpoints cleanly consume physical file payloads."""

    @patch("src.api.main.DocumentParser.parse_file")
    @patch("src.api.main.TaxEngine.run_full_pipeline")
    def test_upload_and_process_endpoint(self, mock_run_pipeline, mock_parse_file):
        """Send mocked multiparts mapped against JSON to verify backend transmission."""
        
        # 1. Setup the dummy Pipeline Response
        mock_parse_file.return_value = "DUMMY TEXT FROM OCR"
        
        dummy_state = ReturnStateObject()
        dummy_state.tax.total_tax_liability = 2000.0
        dummy_state.tax.refund_or_owed = -500.0
        dummy_state.fica.requires_form_843 = True

        mock_run_pipeline.return_value = (["outputs/student_name_1040-NR.pdf"], dummy_state)

        # 2. Setup the Request Payload
        mcq_payload = {
            "tax_year": 2024,
            "visa_type": "F-1",
            "first_us_arrival_year": 2023,
            "tax_residence_country": "China",
            "income_description": "University TA",
            "requires_services": True,
            "is_qualified_expense": False,
        }

        # 3. Simulate HTTP upload
        # We simulate the file as tuple: (filename, content, content_type)
        files = {
            "i94_file": ("my_i94.pdf", b"fake_i94_bytes", "application/pdf"),
            "w2_files": ("my_w2.pdf", b"fake_w2_bytes", "application/pdf")
        }

        data = {
            "mcq_answers_json": json.dumps(mcq_payload)
        }

        response = client.post("/api/v1/upload-and-process", data=data, files=files)

        # 4. Assertions
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["tax_liability"] == 2000.0
        assert response_data["refund_or_owed"] == -500.0
        assert response_data["requires_843_fica_claim"] is True
        assert len(response_data["generated_forms"]) == 1

        # Assert correct arguments landed in the pipeline
        mock_run_pipeline.assert_called_once_with(
            i94_ocr_text="DUMMY TEXT FROM OCR",
            w2_ocr_texts=["DUMMY TEXT FROM OCR"],
            form_1042s_ocr_texts=[],
            mcq_answers=mcq_payload,
        )

        assert mock_parse_file.call_count == 2 # 1 for I94, 1 for W2
