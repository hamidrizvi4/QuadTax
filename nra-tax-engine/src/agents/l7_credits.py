"""L7 Credits Agent — Reconciles all federal withholding against tax liability.

Phase 2: this layer now consumes the full :class:`WithholdingReport`
produced by L3 instead of only summing W-2 + 1042-S withholding. The
report aggregates 1099-INT/DIV/B/MISC withholding and estimated tax
payments, both of which are common for NRAs with US investments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class CreditsAgent:
    """Deterministic federal-credit resolver (refund vs balance due)."""

    def process_credits(self, current_state: "ReturnStateObject") -> "ReturnStateObject":
        """Add every available federal credit and resolve the refund/owed line."""
        report = current_state.withholding_report
        if report:
            # Trust the reconciler if L3 produced one.
            total_credits = float(report.get("federal_total", 0.0))
        else:
            # Backward-compat: legacy callers may bypass the reconciler.
            total_credits = (
                current_state.income.total_w2_withholding
                + current_state.income.total_1042s_withholding
            )

        current_state.tax.total_withholding_credits = total_credits
        current_state.tax.refund_or_owed = (
            current_state.tax.total_tax_liability - total_credits
        )
        current_state.mark_layer_complete("L7")
        return current_state
