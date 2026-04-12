"""
L8 FICA Agent — Evaluates Social Security and Medicare refund claims.

Determines if a Nonresident Alien visa holder (F/J/M/Q) is exempt from FICA
under Section 3121(b)(19) and coordinates the issuance of Form 843 if taxes
were mistakenly withheld. No LLM operations occur in this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.functions.fica_math import FicaCalculator

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class FicaAgent:
    """Deterministic orchestrator for FICA exception processing."""

    def process_fica(self, current_state: ReturnStateObject) -> ReturnStateObject:
        """Route FICA metrics to the mathematical evaluator and mutate state.

        Args:
            current_state: Mutable global state containing residency classification
                           and raw W-2 withholding data.

        Returns:
            Updated ReturnStateObject populated with FICA determinations.
        """
        # ==========================================
        # 1. Deterministic Evaluation
        # ==========================================
        calculator = FicaCalculator()
        
        result = calculator.evaluate_fica_refund(
            status=current_state.residency.status,
            is_exempt_individual=current_state.residency.is_exempt_individual,
            raw_ss_withheld=current_state.income.raw_ss_withheld,
            raw_medicare_withheld=current_state.income.raw_medicare_withheld,
        )

        # ==========================================
        # 2. State Mutation
        # ==========================================
        current_state.fica.is_exempt = result["is_exempt"]
        current_state.fica.incorrect_ss_withheld = result["incorrect_ss_withheld"]
        current_state.fica.incorrect_medicare_withheld = result["incorrect_medicare_withheld"]
        
        # Trigger Document Assembly flag
        requires_843 = result.get("requires_form_843", False)
        if requires_843 and "843" not in current_state.forms_required:
            current_state.forms_required.append("843")

        # Mark finalized
        current_state.mark_layer_complete("L8")

        return current_state
