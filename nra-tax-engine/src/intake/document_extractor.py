"""Document extractor — OCR text extraction + LLM structured parsing.

Accepts raw file bytes per document type and returns a typed OcrResult.
Reuses the existing DocumentParser from ocr_parser.py and safe_parse from _llm_safety.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from src.agents._llm_safety import safe_parse
from src.intake.ocr_parser import DocumentParser


class W2Extracted(BaseModel):
    box_1_wages: float = 0.0
    box_2_fed_withholding: float = 0.0
    box_3_ss_wages: float = 0.0
    box_4_ss_withheld: float = 0.0
    box_5_medicare_wages: float = 0.0
    box_6_medicare_withheld: float = 0.0
    box_17_state_income_tax: float = 0.0
    box_18_local_wages: float = 0.0
    box_19_local_income_tax: float = 0.0
    box_20_locality_name: str = ""
    employer_name: str = Field(default="", description="Employer name from box c")
    employer_ein: str = Field(default="", description="Employer EIN from box b")
    employee_name: str = Field(default="", description="Employee first+last from box e")
    employee_ssn_or_itin: str = Field(default="", description="SSN/ITIN from box a")
    tax_year: int = Field(default=0, description="Tax year on the W-2")


class Form1042SExtracted(BaseModel):
    income_code: int = 0
    gross_income: float = 0.0
    exemption_rate: float = 0.0
    exemption_code: str = ""
    fed_withheld: float = 0.0
    chapter_indicator: int = 3
    recipient_name: str = ""
    withholding_agent_name: str = ""


class Form1099Extracted(BaseModel):
    form_kind: str = ""
    gross_amount: float = 0.0
    fed_withholding: float = 0.0
    payer_name: str = ""


class I94Extracted(BaseModel):
    days_current_year: int = 0
    days_minus_1: int = 0
    days_minus_2: int = 0
    latest_entry_date: str = ""
    latest_class_of_admission: str = ""


class OcrResult(BaseModel):
    i94: Optional[I94Extracted] = None
    w2s: List[W2Extracted] = Field(default_factory=list)
    form_1042s: List[Form1042SExtracted] = Field(default_factory=list)
    form_1099s: List[Form1099Extracted] = Field(default_factory=list)


class DocumentExtractor:
    """Extracts structured fields from tax document bytes using OCR + LLM."""

    def __init__(self, llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI
            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client
        self.parser = DocumentParser()

    def _parse(self, schema, system: str, text: str):
        return safe_parse(
            primary_client=self.llm_client,
            primary_model="gpt-4o-2024-08-06",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format=schema,
        )

    def extract_w2(self, file_bytes: bytes, filename: str) -> W2Extracted:
        text = self.parser.parse_file(file_bytes, filename)
        return self._parse(
            W2Extracted,
            (
                "You are a precise W-2 OCR parser. Extract every field. "
                "For employee_ssn_or_itin return the exact digits shown. "
                "For tax_year look for the year printed on the form. "
                "Return 0.0 for any missing dollar field."
            ),
            f"W-2 OCR text:\n{text}",
        )

    def extract_1042s(self, file_bytes: bytes, filename: str) -> Form1042SExtracted:
        text = self.parser.parse_file(file_bytes, filename)
        return self._parse(
            Form1042SExtracted,
            "You are a precise 1042-S OCR parser. Chapter indicator: 3=NRA withholding, 4=FATCA.",
            f"1042-S OCR text:\n{text}",
        )

    def extract_1099(self, file_bytes: bytes, filename: str) -> Form1099Extracted:
        text = self.parser.parse_file(file_bytes, filename)
        return self._parse(
            Form1099Extracted,
            "You are a precise 1099 OCR parser. Identify form_kind as INT/DIV/B/MISC.",
            f"1099 OCR text:\n{text}",
        )

    def extract_i94(self, file_bytes: bytes, filename: str, tax_year: int = 2025) -> I94Extracted:
        text = self.parser.parse_file(file_bytes, filename)
        return self._parse(
            I94Extracted,
            (
                f"You are a precise I-94 travel data extractor for tax year {tax_year}. "
                "Count days physically present in the US for each year. "
                "Arrival and departure days both count as full days."
            ),
            f"I-94 OCR text:\n{text}",
        )

    def extract_all(
        self,
        i94_bytes: Optional[bytes] = None,
        i94_filename: str = "i94.pdf",
        w2_files: Optional[List[tuple]] = None,
        form_1042s_files: Optional[List[tuple]] = None,
        form_1099_files: Optional[List[tuple]] = None,
        tax_year: int = 2025,
    ) -> OcrResult:
        result = OcrResult()
        if i94_bytes:
            result.i94 = self.extract_i94(i94_bytes, i94_filename, tax_year)
        for file_bytes, filename in (w2_files or []):
            result.w2s.append(self.extract_w2(file_bytes, filename))
        for file_bytes, filename in (form_1042s_files or []):
            result.form_1042s.append(self.extract_1042s(file_bytes, filename))
        for file_bytes, filename in (form_1099_files or []):
            result.form_1099s.append(self.extract_1099(file_bytes, filename))
        return result
