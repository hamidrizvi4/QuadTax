"""
Tax Engine — The Final Orchestrator.

The master execution framework that deterministically ties all agentic reasoning
and physical calculation nodes together in the proper DAG sequence, producing
the final IRS packet.
"""

from typing import Any, Dict, List, Tuple

from src.agents.l1_residency import ResidencyAgent
from src.agents.l3_income import IncomeAgent
from src.agents.l4_treaty import TreatyAgent
from src.agents.l6_tax_calc import TaxCalculationAgent
from src.agents.l7_credits import CreditsAgent
from src.agents.l8_fica import FicaAgent
from src.assembly.form_populator import FormPopulator

from src.orchestrator.state import ReturnStateObject


class TaxEngine:
    """The master orchestrator defining the exact architectural pipeline flow."""

    def __init__(self, llm_client: Any = None):
        """Initialize the single instance of the TaxEngine.

        Args:
            llm_client: The OpenAI client passed to all embedded agents.
        """
        self.llm_client = llm_client

    def run_full_pipeline(
        self,
        i94_ocr_text: str,
        w2_ocr_texts: List[str],
        form_1042s_ocr_texts: List[str],
        mcq_answers: Dict[str, Any],
    ) -> Tuple[List[str], ReturnStateObject]:
        """Execute the continuous tax generation DAG from OCR to generated Form.

        Args:
            i94_ocr_text: The user's travel history text blob.
            w2_ocr_texts: The list of raw text blobs from uploaded W-2s.
            form_1042s_ocr_texts: The list of text blobs from uploaded 1042-S documents.
            mcq_answers: Pre-extracted basic parameters (tax_year, visa_type, etc).

        Returns:
            A list of absolute string paths terminating at the final flat PDF outputs.
        """
        # ==========================================
        # STEP 1: Initialization
        # ==========================================
        state = ReturnStateObject()

        tax_year = mcq_answers["tax_year"]
        visa_type = mcq_answers["visa_type"]
        first_us_arrival_year = mcq_answers["first_us_arrival_year"]
        tax_residence_country = mcq_answers["tax_residence_country"]
        income_description = mcq_answers["income_description"]
        requires_services = mcq_answers["requires_services"]
        is_qualified_expense = mcq_answers["is_qualified_expense"]

        # ==========================================
        # STEP 2: The DAG Sequence
        # ==========================================
        
        # L1: Residency
        residency_agent = ResidencyAgent(llm_client=self.llm_client)
        state = residency_agent.process_residency(
            i94_ocr_text=i94_ocr_text,
            tax_year=tax_year,
            visa_type=visa_type,
            first_us_arrival_year=first_us_arrival_year,
            current_state=state,
        )

        # L3: Income
        income_agent = IncomeAgent(llm_client=self.llm_client)
        state = income_agent.process_income(
            w2_ocr_texts=w2_ocr_texts,
            form_1042s_ocr_texts=form_1042s_ocr_texts,
            requires_services=requires_services,
            is_qualified_expense=is_qualified_expense,
            current_state=state,
        )

        # L4: Treaty
        treaty_agent = TreatyAgent(llm_client=self.llm_client)
        state = treaty_agent.process_treaties(
            tax_residence_country=tax_residence_country,
            income_description=income_description,
            current_state=state,
        )

        # L6: Tax Calculation
        tax_calc_agent = TaxCalculationAgent()
        state = tax_calc_agent.process_tax(current_state=state)

        # L7: Credits
        credits_agent = CreditsAgent()
        state = credits_agent.process_credits(current_state=state)

        # L8: FICA
        fica_agent = FicaAgent()
        state = fica_agent.process_fica(current_state=state)

        # ==========================================
        # STEP 3: Pre-Assembly Validation
        # ==========================================
        required_layers = {"L1", "L3", "L6", "L7", "L8"}
        # Note: L4 might append "L4" or "L4_Skipped", so we don't strictly require "L4" explicitly 
        # below, just the core mathematical/extraction prerequisites
        completed = set(state.completed_layers)
        if not required_layers.issubset(completed):
            raise RuntimeError(f"DAG failed to complete. Missing layers. Completed: {completed}")

        state.ready_for_assembly = True

        # ==========================================
        # STEP 4: PDF Generation (L9)
        # ==========================================
        populator = FormPopulator()
        generated_paths = populator.generate_filing_package(current_state=state)

        return generated_paths, state
