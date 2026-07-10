"""Tests for DocumentExtractor (OCR + LLM structured parsing for /api/v1/ocr)."""

from unittest.mock import MagicMock, patch

import pytest

from src.intake.document_extractor import (
    DocumentExtractor,
    Form1042SExtracted,
    Form1099Extracted,
    I94Extracted,
    OcrResult,
    W2Extracted,
)


def _completion_for(parsed_obj):
    """Build a mock chat-completion object matching the OpenAI structured-output shape."""
    message = MagicMock()
    message.parsed = parsed_obj
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


@pytest.fixture
def mock_ocr_text():
    """Patch DocumentParser.parse_file so no real PDF is needed."""
    with patch(
        "src.intake.document_extractor.DocumentParser.parse_file",
        return_value="DUMMY OCR TEXT",
    ) as parse_mock:
        yield parse_mock


class TestExtractW2:
    def test_extracts_and_returns_w2(self, mock_ocr_text):
        fake_w2 = W2Extracted(
            box_1_wages=32500.0,
            box_2_fed_withholding=4875.0,
            box_4_ss_withheld=2015.0,
            box_6_medicare_withheld=471.25,
            employer_name="New York University",
            employee_name="Wei Chen",
        )
        client = MagicMock()
        client.beta.chat.completions.parse.return_value = _completion_for(fake_w2)

        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_w2(b"%PDF-fake-bytes", "w2.pdf")

        assert isinstance(result, W2Extracted)
        assert result.box_1_wages == 32500.0
        assert result.employer_name == "New York University"
        mock_ocr_text.assert_called_once_with(b"%PDF-fake-bytes", "w2.pdf")
        # The OCR text must be handed to the LLM prompt.
        _, kwargs = client.beta.chat.completions.parse.call_args
        assert "DUMMY OCR TEXT" in kwargs["messages"][1]["content"]
        assert kwargs["response_format"] is W2Extracted
        assert kwargs["temperature"] == 0.0

    def test_defaults_when_llm_omits_fields(self, mock_ocr_text):
        """W2Extracted fields all default to 0.0 / '' so a partial LLM response is still safe."""
        client = MagicMock()
        client.beta.chat.completions.parse.return_value = _completion_for(W2Extracted())
        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_w2(b"bytes", "w2.pdf")
        assert result.box_1_wages == 0.0
        assert result.employer_name == ""


class TestExtract1042S:
    def test_extracts_and_returns_1042s(self, mock_ocr_text):
        fake = Form1042SExtracted(
            income_code=16,
            gross_income=5000.0,
            chapter_indicator=3,
            recipient_name="Wei Chen",
        )
        client = MagicMock()
        client.beta.chat.completions.parse.return_value = _completion_for(fake)

        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_1042s(b"bytes", "1042s.pdf")

        assert isinstance(result, Form1042SExtracted)
        assert result.income_code == 16
        assert result.chapter_indicator == 3
        _, kwargs = client.beta.chat.completions.parse.call_args
        assert kwargs["response_format"] is Form1042SExtracted


class TestExtract1099:
    def test_extracts_and_returns_1099(self, mock_ocr_text):
        fake = Form1099Extracted(form_kind="INT", gross_amount=120.0, fed_withholding=0.0)
        client = MagicMock()
        client.beta.chat.completions.parse.return_value = _completion_for(fake)

        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_1099(b"bytes", "1099.pdf")

        assert isinstance(result, Form1099Extracted)
        assert result.form_kind == "INT"


class TestExtractI94:
    def test_extracts_and_returns_i94(self, mock_ocr_text):
        fake = I94Extracted(
            days_current_year=330,
            days_minus_1=250,
            days_minus_2=130,
            latest_class_of_admission="F-1",
        )
        client = MagicMock()
        client.beta.chat.completions.parse.return_value = _completion_for(fake)

        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_i94(b"bytes", "i94.pdf", tax_year=2025)

        assert isinstance(result, I94Extracted)
        assert result.days_current_year == 330
        assert result.latest_class_of_admission == "F-1"
        # The tax year must be baked into the system prompt so the LLM counts the right year.
        _, kwargs = client.beta.chat.completions.parse.call_args
        assert "2025" in kwargs["messages"][0]["content"]

    def test_tax_year_defaults_to_2025(self, mock_ocr_text):
        client = MagicMock()
        client.beta.chat.completions.parse.return_value = _completion_for(I94Extracted())
        extractor = DocumentExtractor(llm_client=client)
        extractor.extract_i94(b"bytes", "i94.pdf")
        _, kwargs = client.beta.chat.completions.parse.call_args
        assert "2025" in kwargs["messages"][0]["content"]


class TestExtractAll:
    def test_extract_all_wires_every_document_type(self, mock_ocr_text):
        """One call each for I-94, W-2, 1042-S, 1099 — aggregated into OcrResult."""
        fake_i94 = I94Extracted(days_current_year=300)
        fake_w2 = W2Extracted(box_1_wages=10000.0)
        fake_1042s = Form1042SExtracted(income_code=20)
        fake_1099 = Form1099Extracted(form_kind="DIV")

        def side_effect(*args, **kwargs):
            fmt = kwargs["response_format"]
            return _completion_for(
                {
                    I94Extracted: fake_i94,
                    W2Extracted: fake_w2,
                    Form1042SExtracted: fake_1042s,
                    Form1099Extracted: fake_1099,
                }[fmt]
            )

        client = MagicMock()
        client.beta.chat.completions.parse.side_effect = side_effect

        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_all(
            i94_bytes=b"i94-bytes",
            i94_filename="i94.pdf",
            w2_files=[(b"w2-bytes", "w2.pdf")],
            form_1042s_files=[(b"1042s-bytes", "1042s.pdf")],
            form_1099_files=[(b"1099-bytes", "1099.pdf")],
            tax_year=2025,
        )

        assert isinstance(result, OcrResult)
        assert result.i94 is not None
        assert result.i94.days_current_year == 300
        assert len(result.w2s) == 1
        assert result.w2s[0].box_1_wages == 10000.0
        assert len(result.form_1042s) == 1
        assert result.form_1042s[0].income_code == 20
        assert len(result.form_1099s) == 1
        assert result.form_1099s[0].form_kind == "DIV"
        assert client.beta.chat.completions.parse.call_count == 4

    def test_extract_all_handles_no_i94(self, mock_ocr_text):
        """i94_bytes omitted (e.g., F-1 dependent with no travel history) → i94 stays None."""
        client = MagicMock()
        client.beta.chat.completions.parse.return_value = _completion_for(W2Extracted())

        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_all(i94_bytes=None, w2_files=[(b"bytes", "w2.pdf")])

        assert result.i94 is None
        assert len(result.w2s) == 1

    def test_extract_all_empty_input_returns_empty_result(self, mock_ocr_text):
        client = MagicMock()
        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_all()

        assert result.i94 is None
        assert result.w2s == []
        assert result.form_1042s == []
        assert result.form_1099s == []
        client.beta.chat.completions.parse.assert_not_called()

    def test_extract_all_multiple_w2s(self, mock_ocr_text):
        """A filer with more than one on-campus job should get one W2Extracted per document."""
        w2_a = W2Extracted(box_1_wages=5000.0, employer_name="Library")
        w2_b = W2Extracted(box_1_wages=8000.0, employer_name="Dining Hall")
        client = MagicMock()
        client.beta.chat.completions.parse.side_effect = [
            _completion_for(w2_a),
            _completion_for(w2_b),
        ]

        extractor = DocumentExtractor(llm_client=client)
        result = extractor.extract_all(
            w2_files=[(b"a", "w2a.pdf"), (b"b", "w2b.pdf")],
        )

        assert len(result.w2s) == 2
        assert result.w2s[0].employer_name == "Library"
        assert result.w2s[1].employer_name == "Dining Hall"


class TestDocumentExtractorConstruction:
    def test_uses_provided_llm_client(self):
        client = MagicMock()
        extractor = DocumentExtractor(llm_client=client)
        assert extractor.llm_client is client

    def test_default_client_lazily_constructs_openai(self):
        """When no llm_client is passed, DocumentExtractor should lazily build one
        rather than requiring an API key at import time."""
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_openai_cls.return_value = MagicMock()
            extractor = DocumentExtractor()
            mock_openai_cls.assert_called_once()
            assert extractor.llm_client is mock_openai_cls.return_value
