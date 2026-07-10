"""
L1 Residency Agent — Determines the user's tax residency status.

This agent uses an LLM to accurately parse raw OCR text from an I-94 travel
history document, count the number of days physically present in the US
for the required tax years, and then strictly hands those integers off to
the deterministic SubstantialPresenceCalculator for the actual IRS rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from src.agents._llm_safety import safe_parse
from src.functions.spt_calculator import SubstantialPresenceCalculator
from src.llm_config import PRIMARY_MODEL, SECONDARY_MODEL, get_openai_client

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class I94DayCountParams(BaseModel):
    """Schema for the LLM's structured JSON output."""
    days_current_year: int = Field(description="Total days present in the requested tax_year.")
    days_minus_1: int = Field(description="Total days present in tax_year - 1.")
    days_minus_2: int = Field(description="Total days present in tax_year - 2.")


class ResidencyAgent:
    """LLM-powered agent for parsing I-94 travel history.

    This agent acts as a precise OCR extraction tool. It will NOT make any
    tax residency determinations itself. It only counts days and feeds them
    to the deterministic calculation engine.
    """

    def __init__(self, llm_client: Any = None, secondary_llm_client: Any = None):
        """Initialize the residency agent with an OpenAI client.

        Args:
            llm_client: An instance of the OpenAI client. If not provided,
                it will attempt to initialize a default one.
            secondary_llm_client: Optional second client used for dual-extract
                cross-checking of critical numeric fields.
        """
        if llm_client is None:
            self.llm_client = get_openai_client()
        else:
            self.llm_client = llm_client
        self.secondary_llm_client = secondary_llm_client

    def process_residency(
        self,
        i94_ocr_text: str,
        tax_year: int,
        visa_type: str,
        first_us_arrival_year: int,
        current_state: ReturnStateObject,
    ) -> ReturnStateObject:
        """Parse I-94 text, count days present via LLM, and apply SPT formulas.

        Args:
            i94_ocr_text: Raw OCR extracted text showing entry and exit dates.
            tax_year: The current tax year being filed.
            visa_type: The visa category (e.g. "F-1").
            first_us_arrival_year: The first calendar year the individual arrived.
            current_state: The current mutable return state object.

        Returns:
            The updated ReturnStateObject with completed residency state.
        """
        # 1. Ask LLM to extract day counts
        system_prompt = (
            "You are a precise I-94 travel data extraction tool. "
            "Your task is to look at the provided i94_ocr_text and calculate "
            f"the exact number of days the person was physically present in the US "
            f"for the tax year {tax_year}, {tax_year - 1}, and {tax_year - 2}.\n\n"
            "CRITICAL RULE FOR LLM: Arrival and departure days both count as "
            "full days of physical presence. (e.g., Arriving Jan 1 and leaving "
            "Jan 2 is 2 days of presence). Return ONLY the requested JSON schema."
        )

        user_prompt = f"i94_ocr_text:\n{i94_ocr_text}"

        extracted_days: I94DayCountParams = safe_parse(
            primary_client=self.llm_client,
            primary_model=PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=I94DayCountParams,
            secondary_client=self.secondary_llm_client,
            secondary_model=SECONDARY_MODEL if self.secondary_llm_client else None,
            critical_fields=["days_current_year", "days_minus_1", "days_minus_2"],
        )

        # 2. The Deterministic Handoff
        calculator = SubstantialPresenceCalculator()
        result = calculator.evaluate_residency(
            tax_year=tax_year,
            visa_type=visa_type,
            first_us_arrival_year=first_us_arrival_year,
            days_present_current_year=extracted_days.days_current_year,
            days_present_minus_1=extracted_days.days_minus_1,
            days_present_minus_2=extracted_days.days_minus_2,
        )

        # 3. State Mutation
        # Map dictionary values to the ResidencyState pydantic model
        current_state.residency.status = result["status"]
        current_state.residency.spt_days_current_year = result["spt_days_current_year"]
        current_state.residency.is_exempt_individual = result["is_exempt_individual"]
        current_state.residency.exempt_visa_type = result.get("exempt_visa_type")
        current_state.residency.years_in_exempt_status = result["years_in_exempt_status"]

        # Raw (pre-exemption) physical-presence counts — Form 8843 line 4a
        # wants actual days present regardless of exempt status, which
        # spt_days_current_year does not represent for an exempt filer.
        current_state.residency.days_present_current_year = extracted_days.days_current_year
        current_state.residency.days_present_year_minus_1 = extracted_days.days_minus_1
        current_state.residency.days_present_year_minus_2 = extracted_days.days_minus_2

        # Mark layer complete
        current_state.mark_layer_complete("L1")

        return current_state
