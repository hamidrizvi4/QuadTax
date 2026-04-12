"""Tests for the TaxReturnEngine — orchestration and dependency enforcement."""

import pytest

from src.orchestrator.engine import TaxReturnEngine, OrchestrationError
from src.orchestrator.state import ReturnStateObject


class TestTaxReturnEngine:
    """Test suite for the orchestrator engine."""

    def setup_method(self):
        self.engine = TaxReturnEngine()

    def test_dependency_check_no_deps(self):
        """L1 has no dependencies, should always pass."""
        state = ReturnStateObject()
        assert self.engine.check_dependencies("L1", state) is True

    def test_dependency_check_missing(self):
        """L3 requires L1 — should fail if L1 not complete."""
        state = ReturnStateObject()
        with pytest.raises(OrchestrationError):
            self.engine.check_dependencies("L3", state)

    def test_dependency_check_satisfied(self):
        """L3 should pass dependency check when L1 is complete."""
        state = ReturnStateObject()
        state.mark_layer_complete("L1")
        assert self.engine.check_dependencies("L3", state) is True

    def test_dependency_check_l6(self):
        """L6 requires both L1 and L3."""
        state = ReturnStateObject()
        state.mark_layer_complete("L1")
        with pytest.raises(OrchestrationError):
            self.engine.check_dependencies("L6", state)
        state.mark_layer_complete("L3")
        assert self.engine.check_dependencies("L6", state) is True
