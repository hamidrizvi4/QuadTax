"""
Test cases for Issue #5: Skipped Layer L4 Detection.

Test that:
1. ExtractionConfidenceError properly tracks failed layers
2. Treaty eligibility is set to False on confidence error
3. Failed layers are properly removed when layer succeeds
"""

import pytest
from unittest.mock import MagicMock, patch
from src.orchestrator.engine import TaxEngine, ExtractionConfidenceError
from src.orchestrator.state import ReturnStateObject
from src.agents._llm_safety import ExtractionConfidenceError as LLMConfidenceError
def test_extraction_confidence_error_tracks_failed_layer():
    """Test that ExtractionConfidenceError adds layer to failed_layers."""
    engine = TaxEngine()
    state = ReturnStateObject()

    # Mock executor that raises ExtractionConfidenceError
    mock_executor = MagicMock(side_effect=LLMConfidenceError("Low confidence"))

    result = engine._run_layer(
        layer_id="L4",
        function_name="TreatyAgent.process_treaties",
        state=state,
        rationale="Testing confidence error handling",
        executor=mock_executor
    )

    # Should have added L4 to failed_layers
    assert "L4" in result.failed_layers
    # Should have added reason to requires_human_review
    assert any("L4: LLM extraction confidence error" in reason for reason in result.requires_human_review)
    # Treaty should be marked ineligible
    assert result.treaty.is_eligible == False
def test_successful_layer_removes_from_failed_layers():
    """Test that successful layers remove themselves from failed_layers."""
    engine = TaxEngine()
    state = ReturnStateObject()
    state.failed_layers = ["L4"]  # Pre-seed with failed layer

    # Mock successful executor
    mock_executor = MagicMock(return_value=state)

    result = engine._run_layer(
        layer_id="L4",
        function_name="TreatyAgent.process_treaties",
        state=state,
        rationale="Testing successful recovery",
        executor=mock_executor
    )

    # Should have removed L4 from failed_layers
    assert "L4" not in result.failed_layers
    # Should have added to completed_layers
    assert "L4" in result.completed_layers
def test_multiple_failed_layers_handling():
    """Test that multiple failed layers are properly tracked."""
    engine = TaxEngine()
    state = ReturnStateObject()

    # Mock executor that raises on L4, succeeds on L6
    def mock_executor():
        raise LLMConfidenceError("Confidence error")

    # Run L4 (should fail)
    result1 = engine._run_layer(
        layer_id="L4",
        function_name="TreatyAgent.process_treaties",
        state=state,
        rationale="Testing L4 confidence error",
        executor=mock_executor
    )

    assert "L4" in result1.failed_layers
    assert result1.treaty.is_eligible == False

    # Reset state for L6 test
    state2 = ReturnStateObject()
    mock_executor2 = MagicMock(return_value=state2)

    result2 = engine._run_layer(
        layer_id="L4",
        function_name="TreatyAgent.process_treaties",
        state=state2,
        rationale="Testing L4 with successful executor",
        executor=mock_executor2
    )

    # L4 should be in completed, not failed
    assert "L4" in result2.completed_layers
    assert "L4" not in result2.failed_layers
    # Treaty should be eligible again
    assert result2.treaty.is_eligible == True