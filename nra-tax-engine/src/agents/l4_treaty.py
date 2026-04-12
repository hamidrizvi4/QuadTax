"""
L4 Treaty Agent — Maps income descriptions to treaty categories.

This agent acts as a semantic router. It processes a student's real-world
income description and uses an LLM to map it to one of the strict treaty
categories defined in our JSON database. Once mapped, it delegates the actual
application and math to the deterministic TreatyEvaluator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from src.functions.treaty_evaluator import TreatyEvaluator

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class TreatyCategoryMapping(BaseModel):
    """Schema forcing the LLM to output a valid treaty category."""
    mapped_category: Literal["scholarship", "teaching_research", "standard_deduction", "unknown"] = Field(
        description="The strict treaty category the income falls under."
    )


class TreatyAgent:
    """LLM-powered agent for mapping income descriptions to treaty types."""

    def __init__(self, llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI
            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client

    def process_treaties(
        self,
        tax_residence_country: str,
        income_description: str,
        current_state: ReturnStateObject,
    ) -> ReturnStateObject:
        """Route income via LLM and apply deterministic treaty exemptions.

        Args:
            tax_residence_country: The student's home country.
            income_description: Real-world description of income (e.g. "PhD TF").
            current_state: The mutable state object.

        Returns:
            Updated ReturnStateObject with treaty eligibility correctly applied.
        """
        # 1. Safety Check: Treaties generally do not apply to resident aliens.
        if current_state.residency.status != "nonresident_alien":
            current_state.mark_layer_complete("L4_Skipped")
            return current_state

        # 2. LLM Mapping
        system_prompt = (
            "Categorize the user's job description into one of our strict treaty types. "
            "If they teach or do research for a university, map to 'teaching_research'. "
            "If it is a no-work stipend or fellowship, map to 'scholarship'. "
            "If unclear, map to 'unknown'."
        )

        user_prompt = f"Income Description:\n{income_description}"

        completion = self.llm_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=TreatyCategoryMapping,
            temperature=0.0,
        )

        mapping: TreatyCategoryMapping = completion.choices[0].message.parsed
        mapped_category = mapping.mapped_category

        # 3. Determine Target Income
        target_income = 0.0
        if mapped_category == "scholarship":
            target_income = current_state.income.fdap_taxable_total
        elif mapped_category == "teaching_research":
            target_income = current_state.income.eci_taxable_total

        # 4. The Deterministic Handoff
        evaluator = TreatyEvaluator()
        result = evaluator.apply_treaty(
            country=tax_residence_country,
            income_type=mapped_category,
            gross_income=target_income,
            years_present=current_state.residency.years_in_exempt_status,
        )

        # 5. State Mutation
        current_state.treaty.is_eligible = result["is_eligible"]
        current_state.treaty.country = tax_residence_country
        current_state.treaty.article_number = result["article_number"]
        current_state.treaty.exempt_amount_applied = result["exempt_amount_applied"]
        current_state.treaty.applied_to_category = mapped_category

        if result["is_eligible"]:
            if "8833" not in current_state.forms_required:
                current_state.forms_required.append("8833")

        # Mark layer complete
        current_state.mark_layer_complete("L4")

        return current_state
