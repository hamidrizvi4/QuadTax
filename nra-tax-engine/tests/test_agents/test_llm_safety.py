"""Tests for the LLM safety wrapper (Phase 7)."""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field

from src.agents._llm_safety import (
    ExtractionConfidenceError,
    _compare_models,
    _close_enough,
    safe_parse,
)


class FakeBoxes(BaseModel):
    box_1_wages: float = Field(default=0.0)
    box_2_fed_withholding: float = Field(default=0.0)
    box_4_ss_withheld: float = Field(default=0.0)
    employer_name: str = Field(default="")


def _completion(parsed_obj):
    """Build a mock object that matches the OpenAI structured-output shape."""
    msg = MagicMock()
    msg.parsed = parsed_obj
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _client_that_returns(parsed_obj):
    client = MagicMock()
    client.beta.chat.completions.parse.return_value = _completion(parsed_obj)
    return client


class TestCloseEnough:
    def test_within_dollar(self):
        assert _close_enough(30000.0, 30000.5)

    def test_within_half_pct(self):
        assert _close_enough(30000.0, 30100.0)  # 0.33%

    def test_decimal_shift_caught(self):
        assert not _close_enough(30000.0, 3000.0)


class TestCompareModels:
    def test_no_mismatch_when_equal(self):
        a = FakeBoxes(box_1_wages=30000.0)
        b = FakeBoxes(box_1_wages=30000.0)
        assert _compare_models(a, b) == []

    def test_decimal_shift_caught(self):
        a = FakeBoxes(box_1_wages=30000.0)
        b = FakeBoxes(box_1_wages=3000.0)  # OCR ate a zero
        mismatches = _compare_models(a, b)
        assert len(mismatches) == 1
        assert mismatches[0].field == "box_1_wages"

    def test_string_fields_ignored(self):
        a = FakeBoxes(employer_name="Foo")
        b = FakeBoxes(employer_name="Bar")
        assert _compare_models(a, b) == []  # Only numeric fields matter

    def test_critical_field_filter(self):
        a = FakeBoxes(box_1_wages=30000.0, box_2_fed_withholding=4500.0)
        b = FakeBoxes(box_1_wages=30000.0, box_2_fed_withholding=4600.0)
        mismatches = _compare_models(a, b, critical_fields=["box_1_wages"])
        assert mismatches == []  # box_2 disagreement ignored


class TestSafeParse:
    def test_passthrough_without_secondary(self):
        client = _client_that_returns(FakeBoxes(box_1_wages=30000.0))
        result = safe_parse(
            primary_client=client,
            primary_model="gpt-4o",
            messages=[{"role": "user", "content": "ocr"}],
            response_format=FakeBoxes,
        )
        assert result.box_1_wages == 30000.0

    def test_dual_extract_match_returns_primary(self):
        primary = _client_that_returns(FakeBoxes(box_1_wages=30000.0))
        secondary = _client_that_returns(FakeBoxes(box_1_wages=30000.0))
        result = safe_parse(
            primary_client=primary,
            primary_model="gpt-4o",
            secondary_client=secondary,
            secondary_model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ocr"}],
            response_format=FakeBoxes,
        )
        assert result.box_1_wages == 30000.0

    def test_dual_extract_mismatch_raises(self):
        primary = _client_that_returns(FakeBoxes(box_1_wages=30000.0))
        secondary = _client_that_returns(FakeBoxes(box_1_wages=3000.0))
        with pytest.raises(ExtractionConfidenceError) as excinfo:
            safe_parse(
                primary_client=primary,
                primary_model="gpt-4o",
                secondary_client=secondary,
                secondary_model="gpt-4o-mini",
                messages=[{"role": "user", "content": "ocr"}],
                response_format=FakeBoxes,
            )
        assert "box_1_wages" in str(excinfo.value)

    def test_env_var_enables_dual_extract(self, monkeypatch):
        monkeypatch.setenv("QUADTAX_DUAL_EXTRACT", "true")
        primary = MagicMock()
        primary.beta.chat.completions.parse.side_effect = [
            _completion(FakeBoxes(box_1_wages=30000.0)),
            _completion(FakeBoxes(box_1_wages=3000.0)),
        ]
        with pytest.raises(ExtractionConfidenceError):
            safe_parse(
                primary_client=primary,
                primary_model="gpt-4o",
                messages=[{"role": "user", "content": "ocr"}],
                response_format=FakeBoxes,
            )

    def test_secondary_exception_raises_confidence_error(self):
        primary = _client_that_returns(FakeBoxes(box_1_wages=30000.0))
        secondary = MagicMock()
        secondary.beta.chat.completions.parse.side_effect = RuntimeError("timeout")
        with pytest.raises(ExtractionConfidenceError):
            safe_parse(
                primary_client=primary,
                primary_model="gpt-4o",
                secondary_client=secondary,
                secondary_model="gpt-4o-mini",
                messages=[{"role": "user", "content": "ocr"}],
                response_format=FakeBoxes,
            )
