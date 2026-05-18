"""Tests for the TaxEngine orchestration / dependency enforcement.

These cover only the DAG semantics (``check_dependencies``); the full pipeline
is exercised in ``tests/test_integration/test_full_pipeline.py``.
"""

import pytest

from src.orchestrator.engine import (
    LAYER_DEPENDENCIES,
    REQUIRED_LAYERS_FOR_ASSEMBLY,
    OrchestrationError,
    TaxEngine,
    TaxReturnEngine,
)
from src.orchestrator.state import ReturnStateObject


class TestTaxReturnEngine:
    """DAG dependency checks."""

    def setup_method(self):
        self.engine = TaxReturnEngine()

    def test_taxreturnengine_is_taxengine_alias(self):
        assert TaxReturnEngine is TaxEngine

    def test_dependency_check_no_deps(self):
        """L1 has no dependencies — always passes."""
        state = ReturnStateObject()
        assert self.engine.check_dependencies("L1", state) is True

    def test_dependency_check_missing(self):
        """L3 requires L1 — raises when L1 is not complete."""
        state = ReturnStateObject()
        with pytest.raises(OrchestrationError):
            self.engine.check_dependencies("L3", state)

    def test_dependency_check_satisfied(self):
        """L3 passes when L1 is complete."""
        state = ReturnStateObject()
        state.mark_layer_complete("L1")
        assert self.engine.check_dependencies("L3", state) is True

    def test_dependency_check_l6_requires_l1_l3_l4(self):
        """L6 (tax calc) now requires L1, L3, and L4 (treaty) per the production plan."""
        state = ReturnStateObject()
        state.mark_layer_complete("L1")
        state.mark_layer_complete("L3")
        with pytest.raises(OrchestrationError):
            self.engine.check_dependencies("L6", state)
        state.mark_layer_complete("L4")
        assert self.engine.check_dependencies("L6", state) is True

    def test_layer_dependency_graph_shape(self):
        """Sanity check on the published dependency graph."""
        assert LAYER_DEPENDENCIES["L1"] == []
        assert "L1" in LAYER_DEPENDENCIES["L3"]
        assert "L3" in LAYER_DEPENDENCIES["L4"]
        assert set(LAYER_DEPENDENCIES["L6"]) >= {"L1", "L3", "L4"}
        assert "L6" in LAYER_DEPENDENCIES["L7"]

    def test_required_for_assembly_includes_l4(self):
        """Regression: L4 must be among the required-for-assembly layers."""
        assert "L4" in REQUIRED_LAYERS_FOR_ASSEMBLY
