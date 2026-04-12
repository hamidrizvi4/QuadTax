"""
L3 Income Agent — Classifies and categorizes income sources.

This agent loops over raw W-2 and 1042-S OCR strings, extracts strict box
values via LLM, and explicitly maps them to ECI and FDAP buckets using
the deterministic IncomeCodeMapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

from pydantic import BaseModel, Field

from src.functions.code_mapper import IncomeCodeMapper

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class W2Data(BaseModel):
    """Schema for W-2 data extraction."""
    box_1_wages: float = Field(description="Box 1: Wages, tips, other compensation")
    box_2_fed_withholding: float = Field(description="Box 2: Federal income tax withheld")
    box_4_ss_withheld: float = Field(description="Box 4: Social security tax withheld")
    box_6_medicare_withheld: float = Field(description="Box 6: Medicare tax withheld")


class Form1042SData(BaseModel):
    """Schema for 1042-S extraction."""
    box_1_income_code: int = Field(description="Box 1: Income code (2-digit integer)")
    box_2_gross_income: float = Field(description="Box 2: Gross income")
    box_3a_exemption_rate: float = Field(description="Box 3a: Exemption Code/Rate")
    box_3b_exemption_code: str = Field(description="Box 3b: Exemption Code")
    box_7a_fed_withheld: float = Field(description="Box 7a: Federal tax withheld")


class IncomeAgent:
    """LLM-powered agent for income classification.
    
    Acts as an intelligent OCR extractor for tax documents and orchestrates
    the hand-off to the deterministic code mapper.
    """

    def __init__(self, llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI
            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client

    def process_income(
        self,
        w2_ocr_texts: List[str],
        form_1042s_ocr_texts: List[str],
        requires_services: bool,
        is_qualified_expense: bool,
        current_state: ReturnStateObject,
    ) -> ReturnStateObject:
        """Parse W-2s and 1042-S forms, routing them to the correct income buckets.

        Args:
            w2_ocr_texts: List of W-2 OCR strings.
            form_1042s_ocr_texts: List of 1042-S OCR strings.
            requires_services: True if stipend/scholarship required services.
            is_qualified_expense: True if stipend/scholarship is for tuition.
            current_state: Mutable return state object.

        Returns:
            Updated state object with categorized income.
        """
        parsed_w2s = []
        for w2_text in w2_ocr_texts:
            completion = self.llm_client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "You are a precise W-2 OCR parser. Extract the requested fields."},
                    {"role": "user", "content": f"W-2 OCR Text:\n{w2_text}"},
                ],
                response_format=W2Data,
                temperature=0.0,
            )
            parsed_w2s.append(completion.choices[0].message.parsed)

        parsed_1042s = []
        for f1042s_text in form_1042s_ocr_texts:
            completion = self.llm_client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "You are a precise 1042-S OCR parser. Extract the requested fields."},
                    {"role": "user", "content": f"1042-S OCR Text:\n{f1042s_text}"},
                ],
                response_format=Form1042SData,
                temperature=0.0,
            )
            parsed_1042s.append(completion.choices[0].message.parsed)

        # W-2 Aggregation
        total_w2_wages = sum(w2.box_1_wages for w2 in parsed_w2s)

        # 1042-S Routing & Aggregation
        mapper = IncomeCodeMapper()
        total_1042s_gross = 0.0
        routed_eci = 0.0
        routed_fdap = 0.0
        routed_excluded = 0.0

        for f1042_data in parsed_1042s:
            total_1042s_gross += f1042_data.box_2_gross_income
            
            result = mapper.route_1042s_income(
                income_code=f1042_data.box_1_income_code,
                gross_amount=f1042_data.box_2_gross_income,
                requires_services=requires_services,
                is_qualified_expense=is_qualified_expense,
            )
            
            category = result["category"]
            amount = result["taxable_amount"]
            
            if category == "ECI":
                routed_eci += amount
            elif category == "FDAP":
                routed_fdap += amount
            elif category == "EXCLUDED":
                routed_excluded += amount

        # State Mutation
        current_state.income.total_w2_wages = total_w2_wages
        current_state.income.total_1042s_gross = total_1042s_gross
        current_state.income.eci_taxable_total = total_w2_wages + routed_eci
        current_state.income.fdap_taxable_total = routed_fdap
        current_state.income.exempt_scholarship_total = routed_excluded
        
        current_state.income.total_w2_withholding = sum(w2.box_2_fed_withholding for w2 in parsed_w2s)
        current_state.income.total_1042s_withholding = sum(f.box_7a_fed_withheld for f in parsed_1042s)
        current_state.income.raw_ss_withheld = sum(w2.box_4_ss_withheld for w2 in parsed_w2s)
        current_state.income.raw_medicare_withheld = sum(w2.box_6_medicare_withheld for w2 in parsed_w2s)

        current_state.mark_layer_complete("L3")

        return current_state
