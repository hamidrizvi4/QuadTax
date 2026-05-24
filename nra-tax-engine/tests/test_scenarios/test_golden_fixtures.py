"""Golden-fixture validation runner — Phase 8.

Walks the SCENARIOS list, runs each through the orchestrator with mocked
LLM responses, and asserts every value in the scenario's ``expected``
block. A regression in tax math, treaty application, or NY pipeline
fails the matching scenario with a precise diff.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.agents.l1_residency import I94DayCountParams
from src.agents.l3_income import Form1042SData, W2Data
from src.agents.l4_treaty import TreatyCategoryMapping
from src.orchestrator.engine import TaxEngine

from tests.test_scenarios._scenarios import SCENARIOS, SCENARIOS_BY_NAME


class _MockMsg:
    def __init__(self, parsed):
        self.parsed = parsed


class _MockChoice:
    def __init__(self, parsed):
        self.message = _MockMsg(parsed)


class _MockResp:
    def __init__(self, parsed):
        self.choices = [_MockChoice(parsed)]


def _build_router(mocked: dict):
    """Return a side_effect function that maps response_format → parsed model."""
    def router(model, messages, response_format, temperature=0.0):
        if response_format == I94DayCountParams:
            payload = mocked.get("I94DayCountParams") or {
                "days_current_year": 0,
                "days_minus_1": 0,
                "days_minus_2": 0,
            }
            return _MockResp(I94DayCountParams(**payload))
        if response_format == W2Data:
            return _MockResp(W2Data(**mocked["W2Data"]))
        if response_format == Form1042SData:
            return _MockResp(Form1042SData(**mocked["Form1042SData"]))
        if response_format == TreatyCategoryMapping:
            payload = mocked.get("TreatyCategoryMapping") or {"mapped_category": "none"}
            return _MockResp(TreatyCategoryMapping(**payload))
        raise ValueError(f"Unmocked response_format: {response_format}")

    return router


def _resolve(state: Any, dotted_path: str) -> Any:
    """Resolve a dotted attribute path on a Pydantic model."""
    obj: Any = state
    for part in dotted_path.split("."):
        if isinstance(obj, dict):
            obj = obj[part]
        else:
            obj = getattr(obj, part)
    return obj


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_scenario(scenario):
    mock_llm = MagicMock()
    mock_llm.beta.chat.completions.parse.side_effect = _build_router(
        scenario["mocked_llm"]
    )

    with patch("src.orchestrator.engine.FormPopulator.generate_filing_package") as mg:
        mg.return_value = []
        engine = TaxEngine(llm_client=mock_llm, force_assembly=True)
        _paths, state = engine.run_full_pipeline(
            i94_ocr_text=scenario["ocr"]["i94"],
            w2_ocr_texts=scenario["ocr"]["w2s"],
            form_1042s_ocr_texts=scenario["ocr"]["f1042s"],
            mcq_answers=scenario["mcq"],
        )

    # Numeric / string assertions in ``expected``.
    for path, expected_value in scenario["expected"].items():
        actual = _resolve(state, path)
        if isinstance(expected_value, float):
            assert actual == pytest.approx(expected_value, abs=0.5), (
                f"{scenario['name']}: {path} = {actual}, expected {expected_value}"
            )
        else:
            assert actual == expected_value, (
                f"{scenario['name']}: {path} = {actual!r}, expected {expected_value!r}"
            )

    # Required forms membership.
    for form in scenario["required_forms"]:
        assert form in state.forms_required, (
            f"{scenario['name']}: required form {form} missing from {state.forms_required}"
        )

    # Forbidden forms absence.
    for form in scenario["forbidden_forms"]:
        assert form not in state.forms_required, (
            f"{scenario['name']}: forbidden form {form} found in {state.forms_required}"
        )


class TestScenarioInventory:
    """Quick guard rail to detect dropped scenarios during refactors."""

    def test_at_least_12_scenarios(self):
        assert len(SCENARIOS) >= 12

    def test_unique_names(self):
        names = [s["name"] for s in SCENARIOS]
        assert len(names) == len(set(names)), f"Duplicate scenario name(s): {names}"

    def test_lookup_table_coverage(self):
        assert set(SCENARIOS_BY_NAME.keys()) == {s["name"] for s in SCENARIOS}
