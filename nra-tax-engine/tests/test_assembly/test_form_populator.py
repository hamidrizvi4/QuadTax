"""Tests for the Layer 9 PDF Assembly Orchestrator."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.assembly.form_populator import FormPopulator
from src.orchestrator.state import ReturnStateObject


class TestFormPopulator:
    """Test suite ensuring deterministic mappings and physical file orchestration."""

    def test_gatekeeper_validation(self):
        """Ensure the populator hard-fails if the state is not fully calculated."""
        state = ReturnStateObject()
        state._gate_ready_for_assembly = False # Explicitly false

        populator = FormPopulator()
        with pytest.raises(ValueError, match="not ready for assembly"):
            populator.generate_filing_package(state)

    @patch("src.assembly.form_populator.PdfWriter")
    @patch("src.assembly.form_populator.PdfReader")
    @patch("os.path.exists", return_value=True)
    def test_pdf_injection_flow(self, mock_exists, MockReader, MockWriter):
        """Simulate the 1040-NR and 8843 assembly mapping and file generation."""
        # Setup mocks
        mock_writer_instance = MockWriter.return_value
        
        # We need a mock page for the loop `for page in writer.pages`
        mock_page = MagicMock()
        mock_writer_instance.pages = [mock_page]

        # Construct the state explicitly bypassing normal L1-L8 mutations
        state = ReturnStateObject()
        state.tax.total_tax_liability = 1750.0
        state.tax.refund_or_owed = -250.0
        state.residency.years_in_exempt_status = 3
        state.forms_required = ["1040-NR", "8843"]
        state.ready_for_assembly = True

        # Instantiate Populator
        populator = FormPopulator(templates_dir="dummy/dir", outputs_dir="dummy/out")

        # Capture the mappings dynamically to test them
        # (This validates the _get_field_mapping accuracy)
        mapping_1040 = populator._get_field_mapping(state, "1040-NR")
        assert mapping_1040["Line_24_Total_Tax"] == 1750.0
        assert mapping_1040["Line_35a_Refund"] == -250.0

        mapping_8843 = populator._get_field_mapping(state, "8843")
        assert mapping_8843["Part_III_Line_11"] == 3

        # Execute the Package Assembly
        with patch("builtins.open", MagicMock()):
            output_files = populator.generate_filing_package(state, output_dir="outputs/")

        # Assertions
        # 1040-NR and 8843 should have been created
        assert len(output_files) == 2
        assert any("1040-NR" in f for f in output_files)
        assert any("8843" in f for f in output_files)
        
        # The writer's actual file commitment must be invoked exactly twice
        assert mock_writer_instance.write.call_count == 2
        
        # update_page_form_field_values should be called twice (once per form)
        assert mock_writer_instance.update_page_form_field_values.call_count == 2
