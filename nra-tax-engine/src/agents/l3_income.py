"""L3 Income Agent — Classifies and categorizes income sources.

Extracts strict box values from W-2, 1042-S, and 1099-* documents via an LLM
operating in structured-output mode, then hands those typed values to the
deterministic :class:`IncomeCodeMapper` and :class:`WithholdingReconciler`.

Phase 2 changes:
    * Added 1099-INT / 1099-DIV / 1099-B / 1099-MISC parsing.
    * Withholding totals are now computed by :func:`reconcile` and stored
      on ``IncomeState`` for downstream consumption.
    * 1042-S parsing captures the chapter indicator (Ch 3 vs Ch 4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.functions.code_mapper import IncomeCodeMapper
from src.functions.withholding_reconciler import (
    Form1042SEntry,
    Form1099Entry,
    W2Entry,
    reconcile,
)

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class W2Data(BaseModel):
    """W-2 box values used by the engine."""

    box_1_wages: float = Field(description="Box 1: Wages, tips, other compensation")
    box_2_fed_withholding: float = Field(description="Box 2: Federal income tax withheld")
    box_3_ss_wages: float = Field(default=0.0, description="Box 3: Social Security wages")
    box_4_ss_withheld: float = Field(description="Box 4: Social Security tax withheld")
    box_5_medicare_wages: float = Field(default=0.0, description="Box 5: Medicare wages and tips")
    box_6_medicare_withheld: float = Field(description="Box 6: Medicare tax withheld")
    box_17_state_income_tax: float = Field(default=0.0, description="Box 17: State income tax")
    box_18_local_wages: float = Field(default=0.0, description="Box 18: Local wages, tips, etc.")
    box_19_local_income_tax: float = Field(default=0.0, description="Box 19: Local income tax")
    box_20_locality_name: str = Field(default="", description="Box 20: Locality name (e.g., NYC)")


class Form1042SData(BaseModel):
    """1042-S box values used by the engine."""

    box_1_income_code: int = Field(description="Box 1: Income code (2-digit integer)")
    box_2_gross_income: float = Field(description="Box 2: Gross income")
    box_3a_exemption_rate: float = Field(description="Box 3a: Exemption Code/Rate")
    box_3b_exemption_code: str = Field(description="Box 3b: Exemption Code")
    box_7a_fed_withheld: float = Field(description="Box 7a: Federal tax withheld")
    chapter_indicator: int = Field(
        default=3,
        description="Box 3 chapter indicator: 3 = NRA withholding, 4 = FATCA.",
    )


class Form1099Data(BaseModel):
    """Generic 1099-{INT,DIV,B,MISC} extraction."""

    form_kind: Literal["INT", "DIV", "B", "MISC"]
    gross_amount: float = Field(default=0.0)
    fed_withholding: float = Field(default=0.0, description="Federal income tax withheld (box 4).")


class IncomeAgent:
    """LLM-powered agent for income classification."""

    def __init__(self, llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI

            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client

    def _parse(self, schema, system_prompt: str, user_text: str):
        completion = self.llm_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format=schema,
            temperature=0.0,
        )
        return completion.choices[0].message.parsed

    def process_income(
        self,
        w2_ocr_texts: List[str],
        form_1042s_ocr_texts: List[str],
        requires_services: bool,
        is_qualified_expense: bool,
        current_state: "ReturnStateObject",
        form_1099_ocr_texts: Optional[List[str]] = None,
    ) -> "ReturnStateObject":
        """Parse documents, route 1042-S to ECI/FDAP/EXCLUDED, reconcile withholding."""
        form_1099_ocr_texts = form_1099_ocr_texts or []

        parsed_w2s: List[W2Data] = []
        for w2_text in w2_ocr_texts:
            parsed_w2s.append(
                self._parse(
                    W2Data,
                    "You are a precise W-2 OCR parser. Extract the requested fields.",
                    f"W-2 OCR Text:\n{w2_text}",
                )
            )

        parsed_1042s: List[Form1042SData] = []
        for f_text in form_1042s_ocr_texts:
            parsed_1042s.append(
                self._parse(
                    Form1042SData,
                    "You are a precise 1042-S OCR parser. Extract the requested fields. "
                    "Chapter indicator: return 3 for standard NRA withholding, 4 for FATCA.",
                    f"1042-S OCR Text:\n{f_text}",
                )
            )

        parsed_1099s: List[Form1099Data] = []
        for f_text in form_1099_ocr_texts:
            parsed_1099s.append(
                self._parse(
                    Form1099Data,
                    "You are a precise 1099 OCR parser. Identify the form kind "
                    "(INT/DIV/B/MISC) and extract the gross amount and box 4 "
                    "federal income tax withheld.",
                    f"1099 OCR Text:\n{f_text}",
                )
            )

        # --- W-2 aggregation ----------------------------------------------
        total_w2_wages = sum(w2.box_1_wages for w2 in parsed_w2s)

        # --- 1042-S routing -----------------------------------------------
        mapper = IncomeCodeMapper()
        total_1042s_gross = 0.0
        routed_eci = 0.0
        routed_fdap = 0.0
        routed_excluded = 0.0

        for entry in parsed_1042s:
            total_1042s_gross += entry.box_2_gross_income
            result = mapper.route_1042s_income(
                income_code=entry.box_1_income_code,
                gross_amount=entry.box_2_gross_income,
                requires_services=requires_services,
                is_qualified_expense=is_qualified_expense,
            )
            amount = result["taxable_amount"]
            if result["category"] == "ECI":
                routed_eci += amount
            elif result["category"] == "FDAP":
                routed_fdap += amount
            elif result["category"] == "EXCLUDED":
                routed_excluded += amount

        # --- Withholding reconciliation -----------------------------------
        report = reconcile(
            w2s=[
                W2Entry(
                    box_1_wages=w.box_1_wages,
                    box_2_fed_withholding=w.box_2_fed_withholding,
                    box_4_ss_withheld=w.box_4_ss_withheld,
                    box_6_medicare_withheld=w.box_6_medicare_withheld,
                    box_17_state_income_tax=w.box_17_state_income_tax,
                    box_19_local_income_tax=w.box_19_local_income_tax,
                    box_18_local_wages=w.box_18_local_wages,
                    box_20_locality_name=w.box_20_locality_name,
                )
                for w in parsed_w2s
            ],
            f1042s=[
                Form1042SEntry(
                    box_1_income_code=e.box_1_income_code,
                    box_2_gross_income=e.box_2_gross_income,
                    box_7a_fed_withheld=e.box_7a_fed_withheld,
                    chapter_indicator=e.chapter_indicator,
                )
                for e in parsed_1042s
            ],
            f1099s=[
                Form1099Entry(
                    form_kind=e.form_kind,
                    gross_amount=e.gross_amount,
                    fed_withholding=e.fed_withholding,
                )
                for e in parsed_1099s
            ],
        )

        # --- State mutation ----------------------------------------------
        current_state.income.total_w2_wages = total_w2_wages
        current_state.income.total_1042s_gross = total_1042s_gross
        current_state.income.eci_taxable_total = total_w2_wages + routed_eci
        current_state.income.fdap_taxable_total = routed_fdap
        current_state.income.exempt_scholarship_total = routed_excluded

        current_state.income.total_w2_withholding = float(report.federal_w2)
        current_state.income.total_1042s_withholding = float(
            report.federal_1042s_ch3 + report.federal_1042s_ch4
        )
        current_state.income.raw_ss_withheld = float(report.ss_withheld_w2)
        current_state.income.raw_medicare_withheld = float(report.medicare_withheld_w2)

        # Expose the full reconciliation report on the state for later layers.
        current_state.withholding_report = report.to_dict_floats()

        current_state.mark_layer_complete("L3")
        return current_state
