"""Tests for the L3 Income Agent."""

import time
from unittest.mock import MagicMock
import pytest

from src.agents.l3_income import IncomeAgent, W2Data, Form1042SData, Form1099Data
from src.orchestrator.state import ReturnStateObject


def _keyed_side_effect(*maps, delay=0.0):
    """Build a thread-safe ``side_effect`` for ``client.beta.chat.completions.parse``
    that returns a distinguishable, input-keyed value instead of relying on
    call *order* (which the old sequential loop guaranteed, but the
    concurrent ``ThreadPoolExecutor``-based loop does not -- concurrent
    calls can reach the mock in any order).

    ``maps`` is one or more ``{substring_of_user_text: parsed_pydantic_model}``
    dicts. The user message's OCR text is matched by substring so each
    document gets back exactly the value it should, regardless of which
    thread/order the mock is invoked in. This is what actually catches a
    result-mixing bug: if the concurrent code ever paired document A's
    request with document B's response, the wrong substring would match (or
    nothing would) and the assertion on combined state would fail.
    """
    lookup = {}
    for m in maps:
        lookup.update(m)

    def _side_effect(*, model, messages, response_format, temperature):
        if delay:
            time.sleep(delay)
        user_content = messages[1]["content"]
        for key, parsed in lookup.items():
            if key in user_content:
                completion = MagicMock()
                completion.choices = [MagicMock()]
                completion.choices[0].message.parsed = parsed
                return completion
        raise AssertionError(f"No mock response registered for input: {user_content!r}")

    return _side_effect


class TestIncomeAgent:
    """Test suite for the LLM-powered Income Agent."""

    def test_process_income_routing_and_mutation(self):
        """Verify the agent extracts data via LLM and correctly delegates routing to mutate state."""
        mock_client = MagicMock()
        
        # We will pass 1 W-2 and 2 1042-S forms.

        # Fake W-2 data
        fake_w2 = W2Data(
            box_1_wages=15000.0,
            box_2_fed_withholding=1500.0,
            box_4_ss_withheld=0.0,
            box_6_medicare_withheld=0.0
        )

        # Fake 1042-S Data #1: A standard taxable stipend (Code 16, FDAP)
        fake_1042s_1 = Form1042SData(
            box_1_income_code=16,
            box_2_gross_income=5000.0,
            box_3a_exemption_rate=14.0,
            box_3b_exemption_code="00",
            box_7a_fed_withheld=700.0
        )

        # Fake 1042-S Data #2: Another W-2 equivalent income (Code 18, ECI)
        fake_1042s_2 = Form1042SData(
            box_1_income_code=18,
            box_2_gross_income=2000.0,
            box_3a_exemption_rate=0.0,
            box_3b_exemption_code="00",
            box_7a_fed_withheld=200.0
        )

        # Keyed by input substring rather than call order: the W-2 and
        # 1042-S loops now issue their per-document LLM calls concurrently
        # (see IncomeAgent._parse_many), so a plain ordered `side_effect`
        # list is no longer a valid way to mock this -- nothing guarantees
        # which document's request reaches the mock first.
        mock_client.beta.chat.completions.parse.side_effect = _keyed_side_effect(
            {"FAKE W-2 TEXT": fake_w2},
            {
                "FAKE 1042-S TEXT 1": fake_1042s_1,
                "FAKE 1042-S TEXT 2": fake_1042s_2,
            },
        )

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()
        
        # Provide 1 w2 string and 2 1042-s strings to trigger 3 LLM calls
        updated_state = agent.process_income(
            w2_ocr_texts=["FAKE W-2 TEXT"],
            form_1042s_ocr_texts=["FAKE 1042-S TEXT 1", "FAKE 1042-S TEXT 2"],
            requires_services=False,
            is_qualified_expense=False, # This means the Code 16 will route to FDAP
            current_state=state
        )
        
        # Asserts on mock LLM calls
        assert mock_client.beta.chat.completions.parse.call_count == 3
        
        # State Assertion:
        # W-2 Wages = 15000
        # 1042-S Gross = 5000 + 2000 = 7000
        # ECI Total = W-2 + Code 18 = 15000 + 2000 = 17000
        # FDAP Total = Code 16 (Not qualified, no services) = 5000
        # Excluded = 0
        assert updated_state.income.total_w2_wages == 15000.0
        assert updated_state.income.total_1042s_gross == 7000.0
        assert updated_state.income.eci_taxable_total == 17000.0
        assert updated_state.income.fdap_taxable_total == 5000.0
        assert updated_state.income.exempt_scholarship_total == 0.0
        assert "L3" in updated_state.completed_layers

    def test_estimated_payments_from_extras_reach_withholding_report(self):
        """Regression test: reconcile() has always accepted an
        estimated_payments param, but nothing passed it — line 26 of the
        1040-NR was hardcoded to 0 regardless of what the filer entered."""
        mock_client = MagicMock()
        w2_completion = MagicMock()
        w2_completion.choices = [MagicMock()]
        w2_completion.choices[0].message.parsed = W2Data(
            box_1_wages=10000.0, box_2_fed_withholding=1000.0,
            box_4_ss_withheld=0.0, box_6_medicare_withheld=0.0,
        )
        mock_client.beta.chat.completions.parse.side_effect = [w2_completion]

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()
        state.extras.made_estimated_federal_payments = True
        state.extras.estimated_federal_payment_amount = 800.0

        updated_state = agent.process_income(
            w2_ocr_texts=["FAKE W-2 TEXT"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        assert updated_state.withholding_report["federal_estimated_payments"] == 800.0

    def test_no_estimated_payments_when_flag_unset(self):
        mock_client = MagicMock()
        w2_completion = MagicMock()
        w2_completion.choices = [MagicMock()]
        w2_completion.choices[0].message.parsed = W2Data(
            box_1_wages=10000.0, box_2_fed_withholding=1000.0,
            box_4_ss_withheld=0.0, box_6_medicare_withheld=0.0,
        )
        mock_client.beta.chat.completions.parse.side_effect = [w2_completion]

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()
        state.extras.estimated_federal_payment_amount = 800.0  # set but flag False

        updated_state = agent.process_income(
            w2_ocr_texts=["FAKE W-2 TEXT"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        assert updated_state.withholding_report["federal_estimated_payments"] == 0.0

    def test_concurrent_multi_document_extraction_no_result_mixing(self):
        """5 W-2s + 5 1042-S's, each with distinguishable per-call values keyed
        by input text. Proves the ThreadPoolExecutor-based fan-out in
        IncomeAgent._parse_many still pairs each document with its own
        (not some other document's) extraction result -- the failure mode
        concurrent code is uniquely prone to that a sequential loop never
        exhibits."""
        mock_client = MagicMock()

        w2_texts = [f"FAKE W-2 TEXT #{i}" for i in range(5)]
        w2_data = {
            text: W2Data(
                box_1_wages=1000.0 * (i + 1),
                box_2_fed_withholding=100.0 * (i + 1),
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
            for i, text in enumerate(w2_texts)
        }

        f1042s_texts = [f"FAKE 1042-S TEXT #{i}" for i in range(5)]
        # Alternate income codes so ECI vs FDAP routing lets us verify each
        # document landed in the right bucket, not just that totals sum
        # correctly (which could hide a swap between two same-bucket docs).
        f1042s_data = {
            text: Form1042SData(
                box_1_income_code=18 if i % 2 == 0 else 16,  # 18=ECI, 16=FDAP (unqualified)
                box_2_gross_income=100.0 * (i + 1),
                box_3a_exemption_rate=0.0,
                box_3b_exemption_code="00",
                box_7a_fed_withheld=10.0 * (i + 1),
            )
            for i, text in enumerate(f1042s_texts)
        }

        # A small per-call delay makes genuinely-overlapping concurrent
        # calls likely (rather than the thread pool happening to serialize
        # them), so this test actually exercises the race the keyed
        # side_effect is designed to catch.
        mock_client.beta.chat.completions.parse.side_effect = _keyed_side_effect(
            w2_data, f1042s_data, delay=0.01
        )

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()

        updated_state = agent.process_income(
            w2_ocr_texts=w2_texts,
            form_1042s_ocr_texts=f1042s_texts,
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )

        assert mock_client.beta.chat.completions.parse.call_count == 10

        expected_w2_total = sum(1000.0 * (i + 1) for i in range(5))  # 1000+2000+...+5000
        assert updated_state.income.total_w2_wages == expected_w2_total

        expected_1042s_gross = sum(100.0 * (i + 1) for i in range(5))  # 100+200+...+500
        assert updated_state.income.total_1042s_gross == expected_1042s_gross

        # ECI = W-2 total + gross from even-indexed (code 18) 1042-S docs (i=0,2,4 -> amounts 100,300,500)
        expected_eci = expected_w2_total + (100.0 + 300.0 + 500.0)
        assert updated_state.income.eci_taxable_total == expected_eci

        # FDAP = gross from odd-indexed (code 16, unqualified) docs (i=1,3 -> amounts 200,400)
        expected_fdap = 200.0 + 400.0
        assert updated_state.income.fdap_taxable_total == expected_fdap

        # Withholding must likewise reflect every document, not a subset
        # that a mixed-up mapping might have silently dropped or duplicated.
        expected_w2_withholding = sum(100.0 * (i + 1) for i in range(5))
        assert updated_state.income.total_w2_withholding == expected_w2_withholding

    def test_concurrent_extraction_runs_in_parallel_not_sequentially(self):
        """Sanity-check that documents of the same kind are actually
        extracted concurrently (not just correctly): 5 W-2s each behind a
        0.2s mock delay should take much less than 5 * 0.2s wall-clock."""
        mock_client = MagicMock()
        w2_texts = [f"FAKE W-2 TEXT #{i}" for i in range(5)]
        w2_data = {
            text: W2Data(
                box_1_wages=100.0, box_2_fed_withholding=10.0,
                box_4_ss_withheld=0.0, box_6_medicare_withheld=0.0,
            )
            for text in w2_texts
        }
        mock_client.beta.chat.completions.parse.side_effect = _keyed_side_effect(
            w2_data, delay=0.2
        )

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()

        start = time.monotonic()
        agent.process_income(
            w2_ocr_texts=w2_texts,
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        elapsed = time.monotonic() - start

        # Sequential would take >= 1.0s (5 * 0.2s). Concurrent should land
        # close to ~0.2s plus scheduling overhead. Generous threshold to
        # avoid CI flakiness while still clearly distinguishing the two.
        assert elapsed < 0.7

    def test_one_document_failure_fails_whole_request_like_before(self):
        """Preserve the pre-change fail-fast semantics: the original
        sequential loop raised immediately on the first bad document and
        never returned a partial/combined result. The concurrent version
        must behave identically from the caller's point of view -- state is
        left unmutated and the exception propagates."""
        mock_client = MagicMock()

        good_w2 = W2Data(
            box_1_wages=1000.0, box_2_fed_withholding=100.0,
            box_4_ss_withheld=0.0, box_6_medicare_withheld=0.0,
        )

        def side_effect(*, model, messages, response_format, temperature):
            user_content = messages[1]["content"]
            if "BAD" in user_content:
                raise RuntimeError("simulated OCR extraction failure")
            completion = MagicMock()
            completion.choices = [MagicMock()]
            completion.choices[0].message.parsed = good_w2
            return completion

        mock_client.beta.chat.completions.parse.side_effect = side_effect

        agent = IncomeAgent(llm_client=mock_client)
        state = ReturnStateObject()

        with pytest.raises(RuntimeError, match="simulated OCR extraction failure"):
            agent.process_income(
                w2_ocr_texts=["FAKE W-2 TEXT GOOD", "FAKE W-2 TEXT BAD"],
                form_1042s_ocr_texts=[],
                requires_services=False,
                is_qualified_expense=False,
                current_state=state,
            )

        # No partial state mutation: process_income only touches
        # current_state after every document in every loop has parsed
        # successfully, whether sequential or concurrent.
        assert "L3" not in state.completed_layers
        assert state.income.total_w2_wages == 0.0
