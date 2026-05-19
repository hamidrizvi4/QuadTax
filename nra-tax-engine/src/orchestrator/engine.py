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

from src.agents._llm_safety import ExtractionConfidenceError
from src.agents.l1_residency import ResidencyAgent
from src.agents.l3_income import IncomeAgent
from src.agents.l4_treaty import TreatyAgent
from src.agents.l6_tax_calc import TaxCalculationAgent
from src.agents.l7_credits import CreditsAgent
from src.agents.l8_fica import FicaAgent
from src.agents.l9_ny import NYAgent
from src.assembly.form_populator import FormPopulator
from src.functions import estimated_tax_penalty as etp_module
from src.functions import itin_eligibility as itin_module
from src.functions.amt_calculator import AMTCalculator
from src.orchestrator import validators as validators_module
from src.orchestrator.audit import record as audit_record
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
    "L9": ["L7", "L8"],
}

# Layers that must be present in ``completed_layers`` before the engine will
# advance to assembly. L4 is treated as satisfied either by completing
# ("L4") or by an explicit skip ("L4_Skipped") for resident-alien cases.
# L9 (NY) is treated as satisfied by either "L9" or "L9_Skipped".
REQUIRED_LAYERS_FOR_ASSEMBLY: List[str] = ["L1", "L3", "L4", "L6", "L7", "L8", "L9"]


class TaxEngine:
    """Drives the layered DAG from intake OCR text to a generated PDF package."""

    def __init__(self, llm_client: Any = None, force_assembly: bool = False) -> None:
        """Initialize the orchestrator.

        Args:
            llm_client: OpenAI-compatible client. Pass an explicit instance in
                tests to avoid the default lazy ``OpenAI()`` construction.
            force_assembly: When True the engine bypasses the human-review
                gate. The API surfaces this as an explicit acknowledgement of
                every reason in ``state.requires_human_review``.
        """
        self.llm_client = llm_client
        self.force_assembly = force_assembly

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

    def _l9_satisfied(self, state: ReturnStateObject) -> bool:
        """L9 is satisfied if it completed normally or was explicitly skipped."""
        return "L9" in state.completed_layers or "L9_Skipped" in state.completed_layers

    def _run_layer(
        self,
        *,
        layer_id: str,
        function_name: str,
        state: ReturnStateObject,
        rationale: str,
        executor,
    ) -> ReturnStateObject:
        """Execute a layer with audit logging, validator, and confidence-error catching.

        Args:
            layer_id: Layer identifier ("L1", "L3", ...).
            function_name: Human-readable function name for the audit log.
            state: Mutable return state.
            rationale: Plain-English reason for the audit entry.
            executor: Zero-arg callable that runs the layer and returns the
                mutated state.
        """
        inputs_snapshot = state.model_dump()
        try:
            state = executor()
        except ExtractionConfidenceError as exc:
            reason = f"{layer_id}: LLM extraction confidence error — {exc}"
            if reason not in state.requires_human_review:
                state.requires_human_review.append(reason)
            audit_record(
                state,
                layer=layer_id,
                function=function_name,
                inputs=inputs_snapshot,
                outputs={"error": str(exc)},
                rationale=f"Confidence error in {layer_id}; flagged for human review.",
            )
            return state

        audit_record(
            state,
            layer=layer_id,
            function=function_name,
            inputs=inputs_snapshot,
            outputs=state.model_dump(),
            rationale=rationale,
        )
        validators_module.run_validator(state, layer_id)
        return state

    def _compute_phase3_addons(self, state: ReturnStateObject) -> None:
        """Run AMT, ITIN, and estimated-tax-penalty evaluations and mutate state."""
        # AMT — taxable income approximated as eci_taxable_total − exempt; this
        # is a sound first-pass for student returns. A future revision will use
        # the precise Form 1040-NR line 15 figure once the populator emits it.
        taxable = max(
            0.0,
            float(state.income.eci_taxable_total) - float(state.treaty.exempt_amount_applied),
        )
        amt = AMTCalculator(tax_year=state.tax_year).compute(
            taxable_income=taxable,
            regular_tax=float(state.tax.eci_tax_liability),
            filing_status=state.identity.filing_status,
        )
        state.amt = amt.to_dict_floats()
        if amt.binds and "6251" not in state.forms_required:
            state.forms_required.append("6251")

        # ITIN — drive Form W-7 when no SSN.
        ident = state.identity
        has_ssn = bool(ident.ssn)
        has_itin = bool(ident.itin)
        itin_result = itin_module.evaluate(
            has_ssn=has_ssn,
            has_existing_itin=has_itin,
            is_student=(state.residency.exempt_visa_type or "").upper()
            in {"F-1", "J-1", "M-1", "Q-1"},
            claiming_treaty_benefit=state.treaty.is_eligible,
            current_tax_year=state.tax_year,
        )
        state.itin_eligibility = itin_result.to_dict()
        ident.requires_w7_application = itin_result.needs_w7
        if itin_result.needs_w7 and "W-7" not in state.forms_required:
            state.forms_required.append("W-7")

        # Estimated tax penalty — surface Form 2210 attachment if no safe harbor.
        penalty_result = etp_module.evaluate(
            current_year_total_tax=float(state.tax.total_tax_liability),
            total_withholding_and_estimated=float(state.tax.total_withholding_credits),
        )
        state.estimated_tax_penalty = penalty_result.to_dict_floats()
        if penalty_result.must_attach_form_2210 and "2210" not in state.forms_required:
            state.forms_required.append("2210")

    def run_full_pipeline(
        self,
        i94_ocr_text: str,
        w2_ocr_texts: List[str],
        form_1042s_ocr_texts: List[str],
        mcq_answers: Dict[str, Any],
        initial_state: ReturnStateObject | None = None,
    ) -> Tuple[List[str], ReturnStateObject]:
        """Execute the continuous tax generation DAG from OCR to generated forms.

        Args:
            i94_ocr_text: Raw text extracted from the I-94 travel history PDF.
            w2_ocr_texts: One raw text blob per uploaded W-2.
            form_1042s_ocr_texts: One raw text blob per uploaded 1042-S.
            mcq_answers: Intake answers (tax_year, visa_type, etc.).
            initial_state: Optional pre-populated ReturnStateObject (e.g. from
                :meth:`MCQRouter.populate_state`). Phase-3 add-ons (AMT, ITIN,
                Form 2210) read identity fields, so passing a seeded state
                yields more accurate W-7 / AMT detection. When omitted, the
                engine constructs a fresh state and the identity is empty
                until the API re-seeds it after the call.

        Returns:
            Tuple of ``(generated_pdf_paths, final_state)``.
        """
        state = initial_state if initial_state is not None else ReturnStateObject()
        state.tax_year = mcq_answers["tax_year"]

        tax_year = mcq_answers["tax_year"]
        visa_type = mcq_answers["visa_type"]
        first_us_arrival_year = mcq_answers["first_us_arrival_year"]
        tax_residence_country = mcq_answers["tax_residence_country"]
        income_description = mcq_answers["income_description"]
        requires_services = mcq_answers["requires_services"]
        is_qualified_expense = mcq_answers["is_qualified_expense"]

        # L1 — Residency
        residency_agent = ResidencyAgent(llm_client=self.llm_client)
        state = self._run_layer(
            layer_id="L1",
            function_name="ResidencyAgent.process_residency",
            state=state,
            rationale="OCR'd I-94 day counts handed to SPT calculator.",
            executor=lambda: residency_agent.process_residency(
                i94_ocr_text=i94_ocr_text,
                tax_year=tax_year,
                visa_type=visa_type,
                first_us_arrival_year=first_us_arrival_year,
                current_state=state,
            ),
        )

        # L3 — Income
        self.check_dependencies("L3", state)
        income_agent = IncomeAgent(llm_client=self.llm_client)
        state = self._run_layer(
            layer_id="L3",
            function_name="IncomeAgent.process_income",
            state=state,
            rationale="W-2 + 1042-S + 1099 OCR routed through code_mapper and withholding_reconciler.",
            executor=lambda: income_agent.process_income(
                w2_ocr_texts=w2_ocr_texts,
                form_1042s_ocr_texts=form_1042s_ocr_texts,
                requires_services=requires_services,
                is_qualified_expense=is_qualified_expense,
                current_state=state,
            ),
        )

        # L4 — Treaty
        self.check_dependencies("L4", state)
        treaty_agent = TreatyAgent(llm_client=self.llm_client)
        state = self._run_layer(
            layer_id="L4",
            function_name="TreatyAgent.process_treaties",
            state=state,
            rationale="LLM classified income; deterministic evaluator applied every matching article.",
            executor=lambda: treaty_agent.process_treaties(
                tax_residence_country=tax_residence_country,
                income_description=income_description,
                current_state=state,
            ),
        )

        # L6 — Tax Calculation (depends on L4 outcome, including the skip case)
        if not self._l4_satisfied(state):
            raise OrchestrationError(
                "L4 must complete or be explicitly skipped before L6 runs."
            )
        tax_calc_agent = TaxCalculationAgent()
        state = self._run_layer(
            layer_id="L6",
            function_name="TaxCalculationAgent.process_tax",
            state=state,
            rationale="ECI brackets applied to post-treaty income; FDAP at statutory or treaty rate.",
            executor=lambda: tax_calc_agent.process_tax(current_state=state),
        )

        # L7 — Credits
        self.check_dependencies("L7", state)
        credits_agent = CreditsAgent()
        state = self._run_layer(
            layer_id="L7",
            function_name="CreditsAgent.process_credits",
            state=state,
            rationale="Federal credits summed from the withholding reconciler.",
            executor=lambda: credits_agent.process_credits(current_state=state),
        )

        # L8 — FICA
        self.check_dependencies("L8", state)
        fica_agent = FicaAgent()
        state = self._run_layer(
            layer_id="L8",
            function_name="FicaAgent.process_fica",
            state=state,
            rationale="FICA exemption check and Form 843 trigger.",
            executor=lambda: fica_agent.process_fica(current_state=state),
        )

        # L9 — NY pipeline. Runs only when ny_intake is provided OR when the
        # filer's US address is in NY; otherwise marked as skipped so the
        # assembly gate is still satisfied for non-NY filers.
        ny_intake = mcq_answers.get("ny_intake")
        if ny_intake is not None or state.identity.us_state == "NY":
            self.check_dependencies("L9", state)
            ny_agent = NYAgent()
            state = ny_agent.process_ny(current_state=state, ny_intake=ny_intake)
        else:
            state.mark_layer_complete("L9_Skipped")

        # Phase 3 post-tax computations: AMT, ITIN, estimated-tax penalty.
        self._compute_phase3_addons(state)

        # Human-in-loop gate. Any populated reason blocks assembly until the
        # API caller passes ``force_assembly=True``.
        if state.requires_human_review and not self.force_assembly:
            raise OrchestrationError(
                "Human review required before assembly: "
                + " | ".join(state.requires_human_review)
            )

        # Pre-assembly validation
        completed = set(state.completed_layers)
        # Treat L4 / L9 as satisfied by either of their two terminal markers.
        if self._l4_satisfied(state):
            completed.add("L4")
        if self._l9_satisfied(state):
            completed.add("L9")
        missing = [layer for layer in REQUIRED_LAYERS_FOR_ASSEMBLY if layer not in completed]
        if missing:
            raise OrchestrationError(
                f"DAG failed to complete. Missing layers: {missing}. "
                f"Completed: {sorted(state.completed_layers)}."
            )

        state.ready_for_assembly = True

        # L9 — Assembly
        populator = FormPopulator(tax_year=state.tax_year)
        generated_paths = populator.generate_filing_package(current_state=state)

        return generated_paths, state


# Backwards-compatible alias used in some tests and external code.
TaxReturnEngine = TaxEngine
