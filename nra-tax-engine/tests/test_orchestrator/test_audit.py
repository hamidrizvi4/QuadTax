"""Tests for the audit log."""

import json
import os
from pathlib import Path

from src.orchestrator.audit import _stable_hash, record
from src.orchestrator.state import ReturnStateObject


class TestAuditTrail:
    def test_record_appends_entry(self):
        state = ReturnStateObject()
        entry = record(
            state,
            layer="L3",
            function="IncomeAgent.process_income",
            inputs={"w2_count": 1},
            outputs={"total_wages": 30000.0},
            rationale="Routed W-2 box 1 wages through code mapper.",
        )
        assert len(state.audit_trail) == 1
        assert state.audit_trail[0]["layer"] == "L3"
        assert state.audit_trail[0]["function"] == "IncomeAgent.process_income"
        assert entry.layer == "L3"

    def test_hashes_are_deterministic(self):
        a = _stable_hash({"x": 1, "y": 2})
        b = _stable_hash({"y": 2, "x": 1})
        assert a == b, "Hash must be order-independent"

    def test_hashes_change_when_inputs_change(self):
        a = _stable_hash({"x": 1})
        b = _stable_hash({"x": 2})
        assert a != b

    def test_record_persists_to_jsonl_when_env_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("QUADTAX_AUDIT_DIR", str(tmp_path))
        state = ReturnStateObject()
        state.filing_id = "fixture-001"

        record(
            state,
            layer="L1",
            function="SubstantialPresenceCalculator.evaluate_residency",
            inputs={"days_current_year": 300},
            outputs={"status": "nonresident_alien"},
            rationale="F-1 in year 2 of 5 — exempt under §7701(b)(5).",
        )
        log_path = tmp_path / "fixture-001" / "audit.jsonl"
        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["filing_id"] == "fixture-001"
        assert parsed["layer"] == "L1"

    def test_record_includes_preview_for_dict_inputs(self):
        state = ReturnStateObject()
        record(
            state,
            layer="L4",
            function="TreatyAgent",
            inputs={"country": "CN", "income_description": "TA"},
            outputs={"article_id": "20(c)"},
            rationale="Mapped to student_personal_services category.",
        )
        entry = state.audit_trail[0]
        assert entry["inputs_preview"]["country"] == "CN"
