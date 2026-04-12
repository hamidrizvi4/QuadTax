"""
L7 Credits Agent — Reconciles withholdings against tax liabilities.

Calculates the final federal balance (refund or amount owed) by adding
up all tax credits (W-2 and 1042-S withholdings) and subtracting them
from the mathematically determined total tax liability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class CreditsAgent:
    """Deterministic orchestrator for federal credit resolution."""

    def process_credits(self, current_state: ReturnStateObject) -> ReturnStateObject:
        """Add all available credits and resolve final amount owed/refunded.

        Args:
            current_state: State object holding liability and withholding metrics.

        Returns:
            Updated state object with finalized tax calculations.
        """
        # ==========================================
        # 1. Tally Total Credits
        # ==========================================
        total_credits = (
            current_state.income.total_w2_withholding + 
            current_state.income.total_1042s_withholding
        )

        # ==========================================
        # 2. Determine Ledger Balance
        # ==========================================
        # If liability - credits is positive, they owe money.
        # If liability - credits is negative, they get a refund.
        current_state.tax.total_withholding_credits = total_credits
        current_state.tax.refund_or_owed = current_state.tax.total_tax_liability - total_credits

        # ==========================================
        # 3. State Mutation
        # ==========================================
        current_state.mark_layer_complete("L7")

        return current_state
