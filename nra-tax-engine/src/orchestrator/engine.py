"""Tax Engine — orchestrator that drives the layered DAG.

The engine wires together the LLM-powered extraction agents (L1, L3, L4) and
the deterministic calculators (L6, L7, L8) defined in
``src/functions/``, mutating a single :class:`ReturnStateObject` as each
layer completes. After all required layers finish, the populator generates
the IRS/state PDF package.

Phase 0 changes:
    * L4 (treaty) is now a hard prerequisite for assembly — previously it was
      excluded from ``required_layers`` and could silently skip.
    * Added :class:`OrchestrationError` and :meth:`check_dependencies` so the
      engine's DAG semantics are independently testable.
    * Exposed ``TaxReturnEngine`` as an alias for :class:`TaxEngine`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.agents.l1_residency import ResidencyAgent
from src.agents.l3_income import IncomeAgent
from src.agents.l4_treaty import TreatyAgent
from src.agents.l6_tax_calc import TaxCalculationAgent
from src.agents.l7_credits import CreditsAgent
from src.agents.l8_fica import FicaAgent
from src.assembly.form_populator import FormPopulator
from src.orchestrator.state import ReturnStateObject


class OrchestrationError(RuntimeError):
    """Raised when a layer's dependencies are not satisfied."""


# Layer dependency graph. Each key is a layer id; each value is the set of
# layers that must be marked complete before that layer may run.
LAYER_DEPENDENCIES: Dict[str, List[str]] = {
    "L1": [],
    "L3": ["L1"],
    "L4": ["L1", "L3"],
    "L6": ["L1", "L3", "L4"],
    "L7": ["L6"],
    "L8": ["L1", "L3"],
}

# Layers that must be present in ``completed_layers`` before the engine will
# advance to assembly. L4 is treated as satisfied either by completing
# ("L4") or by an explicit skip ("L4_Skipped") for resident-alien cases.
REQUIRED_LAYERS_FOR_ASSEMBLY: List[str] = ["L1", "L3", "L4", "L6", "L7", "L8"]


class TaxEngine:
    """Drives the layered DAG from intake OCR text to a generated PDF package."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    def check_dependencies(self, layer: str, state: ReturnStateObject) -> bool:
        """Verify that all prerequisites of ``layer`` are marked complete.

        Args:
            layer: Identifier of the layer being checked (e.g. ``"L3"``).
            state: Current return state object.

        Returns:
            ``True`` when every dependency has been marked complete.

        Raises:
            OrchestrationError: If any dependency is missing from
                ``state.completed_layers``.
        """
        deps = LAYER_DEPENDENCIES.get(layer, [])
        completed = set(state.completed_layers)
        missing = [d for d in deps if d not in completed]
        if missing:
            raise OrchestrationError(
                f"Layer {layer} cannot run: missing dependencies {missing}. "
                f"Completed so far: {sorted(completed)}."
            )
        return True

    def _l4_satisfied(self, state: ReturnStateObject) -> bool:
        """L4 is satisfied if it completed normally or was explicitly skipped."""
        return "L4" in state.completed_layers or "L4_Skipped" in state.completed_layers

    def run_full_pipeline(
        self,
        i94_ocr_text: str,
        w2_ocr_texts: List[str],
        form_1042s_ocr_texts: List[str],
        mcq_answers: Dict[str, Any],
    ) -> Tuple[List[str], ReturnStateObject]:
        """Execute the continuous tax generation DAG from OCR to generated forms.

        Args:
            i94_ocr_text: Raw text extracted from the I-94 travel history PDF.
            w2_ocr_texts: One raw text blob per uploaded W-2.
            form_1042s_ocr_texts: One raw text blob per uploaded 1042-S.
            mcq_answers: Intake answers (tax_year, visa_type, etc.).

        Returns:
            Tuple of ``(generated_pdf_paths, final_state)``.
        """
        state = ReturnStateObject()

        tax_year = mcq_answers["tax_year"]
        visa_type = mcq_answers["visa_type"]
        first_us_arrival_year = mcq_answers["first_us_arrival_year"]
        tax_residence_country = mcq_answers["tax_residence_country"]
        income_description = mcq_answers["income_description"]
        requires_services = mcq_answers["requires_services"]
        is_qualified_expense = mcq_answers["is_qualified_expense"]

        # L1 — Residency
        residency_agent = ResidencyAgent(llm_client=self.llm_client)
        state = residency_agent.process_residency(
            i94_ocr_text=i94_ocr_text,
            tax_year=tax_year,
            visa_type=visa_type,
            first_us_arrival_year=first_us_arrival_year,
            current_state=state,
        )

        # L3 — Income
        self.check_dependencies("L3", state)
        income_agent = IncomeAgent(llm_client=self.llm_client)
        state = income_agent.process_income(
            w2_ocr_texts=w2_ocr_texts,
            form_1042s_ocr_texts=form_1042s_ocr_texts,
            requires_services=requires_services,
            is_qualified_expense=is_qualified_expense,
            current_state=state,
        )

        # L4 — Treaty
        self.check_dependencies("L4", state)
        treaty_agent = TreatyAgent(llm_client=self.llm_client)
        state = treaty_agent.process_treaties(
            tax_residence_country=tax_residence_country,
            income_description=income_description,
            current_state=state,
        )

        # L6 — Tax Calculation (depends on L4 outcome, including the skip case)
        if not self._l4_satisfied(state):
            raise OrchestrationError(
                "L4 must complete or be explicitly skipped before L6 runs."
            )
        tax_calc_agent = TaxCalculationAgent()
        state = tax_calc_agent.process_tax(current_state=state)

        # L7 — Credits
        self.check_dependencies("L7", state)
        credits_agent = CreditsAgent()
        state = credits_agent.process_credits(current_state=state)

        # L8 — FICA
        self.check_dependencies("L8", state)
        fica_agent = FicaAgent()
        state = fica_agent.process_fica(current_state=state)

        # Pre-assembly validation
        completed = set(state.completed_layers)
        # Treat L4 as satisfied by either of its two terminal markers.
        if self._l4_satisfied(state):
            completed.add("L4")
        missing = [layer for layer in REQUIRED_LAYERS_FOR_ASSEMBLY if layer not in completed]
        if missing:
            raise OrchestrationError(
                f"DAG failed to complete. Missing layers: {missing}. "
                f"Completed: {sorted(state.completed_layers)}."
            )

        state.ready_for_assembly = True

        # L9 — Assembly
        populator = FormPopulator()
        generated_paths = populator.generate_filing_package(current_state=state)

        return generated_paths, state


# Backwards-compatible alias used in some tests and external code.
TaxReturnEngine = TaxEngine
