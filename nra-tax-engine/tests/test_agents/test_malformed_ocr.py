"""Tests for how L1/L3 agents behave on garbled, truncated, non-English, and
otherwise messy real-world OCR input.

Every existing agent test (test_l1_residency.py, test_l3_income.py) mocks
the LLM call with a single clean, well-formed structured response and a
tidy placeholder OCR string ("FAKE RECORD", "FAKE W-2 TEXT", ...). None of
them exercise what happens when:

    1. The raw OCR text handed to the LLM prompt is itself garbled,
       truncated, or in a language other than English (this product's
       actual users are international students/scholars whose I-94, W-2,
       and 1042-S scans routinely contain non-Latin scripts, watermark
       noise, and partial-page truncation).
    2. The LLM's structured-output call raises outright (refusal, timeout,
       schema-validation failure upstream).
    3. The LLM *does* return a well-formed object, but with implausible
       values (negative day counts, absurd wage figures) that a garbled
       source document could plausibly produce.

This file focuses on the mocked-LLM-response boundary (like the existing
agent test suites do) plus the two safety nets the engine has for exactly
this failure class:

    * ``src.agents._llm_safety.safe_parse`` / ``ExtractionConfidenceError``
      — raised when a secondary ("second opinion") extraction disagrees
      with the primary, or when the secondary call itself fails.
    * ``src.orchestrator.validators`` — post-layer reasonability checks
      that flag implausible-but-well-typed values for human review.

Two real gaps were found and fixed while writing this coverage (see
``TestL1PriorYearDayBoundsFix`` and ``TestL3NegativeWithholdingFix`` below):
raw I-94 day counts for tax_year-1/tax_year-2, and W-2/1042-S federal
withholding totals, were assigned onto ``ReturnStateObject`` straight from
LLM extraction with no validator ever checking them, even though the
Pydantic ``ge=0``/``le=366`` field constraints on those exact fields imply
they should be. State mutation doesn't use Pydantic's ``validate_assignment``,
so those constraints were silently inert on assignment. See
``src/orchestrator/validators.py`` for the fix.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.agents._llm_safety import ExtractionConfidenceError
from src.agents.l1_residency import I94DayCountParams, ResidencyAgent
from src.agents.l3_income import Form1042SData, IncomeAgent, W2Data
from src.orchestrator.state import ReturnStateObject
from src.orchestrator.validators import validate_post_l1, validate_post_l3


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _completion_for(parsed_obj):
    """Build a mock chat-completion object matching the OpenAI structured-
    output shape (same convention as test_document_extractor.py)."""
    message = MagicMock()
    message.parsed = parsed_obj
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _client_returning(*parsed_objs):
    """MagicMock client whose .parse() yields parsed_objs in sequence."""
    client = MagicMock()
    if len(parsed_objs) == 1:
        client.beta.chat.completions.parse.return_value = _completion_for(parsed_objs[0])
    else:
        client.beta.chat.completions.parse.side_effect = [
            _completion_for(o) for o in parsed_objs
        ]
    return client


# A grab-bag of realistic messy OCR strings: non-English (Chinese, Spanish),
# truncated mid-field, and outright garbled/binary-noise text. These are fed
# as the raw *input* text — the mocked LLM response models what a real
# extraction model would (or wouldn't) manage to pull out of them.
NON_ENGLISH_CHINESE_I94_TEXT = (
    "美国海关和边境保护局 I-94 到达/离境记录\n"
    "姓名: 陈伟\n签证类型: F-1\n入境日期: 2024年01月15日\n"
    "离境日期: 2024年05月20日\n出生国: 中国\n"
)
NON_ENGLISH_SPANISH_W2_TEXT = (
    "Formulario W-2 Comprobante de Salarios e Impuestos\n"
    "Empleador: Universidad de Nueva York\n"
    "Casilla 1 Salarios: 18,400.00\n"
    "Casilla 2 Impuesto federal retenido: 1,840.00\n"
)
TRUNCATED_OCR_TEXT = "I-94 Arrival/Depa"  # cut off mid-word, page 2 missing
GARBLED_OCR_TEXT = (
    "\x0c\x00I—94  ﾄﾗﾍﾞﾙ  ﾚｺｰﾄﾞ\n"
    "Ent灯y: 0΄1/1΄5/2024 ##@@ Exit: ▯▯/▯▯/▯▯▯▯\n"
    "%%%$$$ SCAN ERROR RETRY %%%$$$\n"
)
EMPTY_OCR_TEXT = ""


# ---------------------------------------------------------------------------
# L1 Residency Agent — garbled/non-English/implausible I-94 extraction
# ---------------------------------------------------------------------------


class TestL1NonEnglishAndGarbledInputIsForwarded:
    """The agent must not choke on the raw OCR text itself — it's opaque
    bytes to the agent, the LLM is responsible for understanding it. These
    tests confirm the messy text reaches the prompt intact and a normal
    (plausible) LLM response still flows through cleanly."""

    def test_chinese_i94_text_forwarded_and_normal_response_not_flagged(self):
        client = _client_returning(
            I94DayCountParams(days_current_year=126, days_minus_1=0, days_minus_2=0)
        )
        agent = ResidencyAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_residency(
            i94_ocr_text=NON_ENGLISH_CHINESE_I94_TEXT,
            tax_year=2024,
            visa_type="F-1",
            first_us_arrival_year=2024,
            current_state=state,
        )

        call_kwargs = client.beta.chat.completions.parse.call_args.kwargs
        assert NON_ENGLISH_CHINESE_I94_TEXT in call_kwargs["messages"][1]["content"]
        assert updated.residency.days_present_current_year == 126
        validate_post_l1(updated)
        assert updated.requires_human_review == []

    def test_truncated_ocr_text_still_calls_llm(self):
        """A page-2-missing scan shouldn't crash the agent before the LLM
        even gets a chance to try; the raw text is passed through as-is."""
        client = _client_returning(
            I94DayCountParams(days_current_year=0, days_minus_1=0, days_minus_2=0)
        )
        agent = ResidencyAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_residency(
            i94_ocr_text=TRUNCATED_OCR_TEXT,
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2024,
            current_state=state,
        )
        client.beta.chat.completions.parse.assert_called_once()
        assert "L1" in updated.completed_layers

    def test_empty_ocr_text_still_calls_llm_and_does_not_crash(self):
        client = _client_returning(
            I94DayCountParams(days_current_year=0, days_minus_1=0, days_minus_2=0)
        )
        agent = ResidencyAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_residency(
            i94_ocr_text=EMPTY_OCR_TEXT,
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2024,
            current_state=state,
        )
        assert updated.residency.days_present_current_year == 0
        validate_post_l1(updated)
        assert updated.requires_human_review == []

    def test_binary_noise_ocr_text_forwarded_verbatim(self):
        client = _client_returning(
            I94DayCountParams(days_current_year=90, days_minus_1=0, days_minus_2=0)
        )
        agent = ResidencyAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_residency(
            i94_ocr_text=GARBLED_OCR_TEXT,
            tax_year=2024,
            visa_type="F-1",
            first_us_arrival_year=2024,
            current_state=state,
        )
        call_kwargs = client.beta.chat.completions.parse.call_args.kwargs
        assert GARBLED_OCR_TEXT in call_kwargs["messages"][1]["content"]
        assert "L1" in updated.completed_layers


class TestL1PriorYearDayBoundsFix:
    """Regression coverage for the gap found & fixed in this pass: garbled
    I-94 OCR text can make the LLM return an implausible day count for
    tax_year-1 / tax_year-2 (unlike the current-year count, these were
    never bounds-checked anywhere). Those raw values are printed verbatim
    on Form 8843 Part I line 4a and Schedule OI item H — a negative or
    >366 figure reaching a filed federal form, un-flagged, is the exact
    silent-wrong-answer failure this product must never have."""

    @staticmethod
    def _run(days_current, days_minus_1, days_minus_2):
        client = _client_returning(
            I94DayCountParams(
                days_current_year=days_current,
                days_minus_1=days_minus_1,
                days_minus_2=days_minus_2,
            )
        )
        agent = ResidencyAgent(llm_client=client)
        state = ReturnStateObject()
        updated = agent.process_residency(
            i94_ocr_text=GARBLED_OCR_TEXT,
            tax_year=2024,
            visa_type="H-1B",
            first_us_arrival_year=2020,
            current_state=state,
        )
        validate_post_l1(updated)
        return updated

    def test_negative_prior_year_1_days_flagged(self):
        """OCR misread a departure date, producing a negative day count for
        tax_year - 1 (e.g. an exit date parsed as earlier than an entry
        date). Must reach a human, not silently distort the SPT weighted
        total or print a negative day count on Form 8843."""
        updated = self._run(days_current=200, days_minus_1=-99999, days_minus_2=10)
        assert updated.residency.days_present_year_minus_1 == -99999
        assert any(
            "tax_year - 1" in r and "outside 0-366" in r
            for r in updated.requires_human_review
        ), updated.requires_human_review

    def test_negative_prior_year_2_days_flagged(self):
        updated = self._run(days_current=100, days_minus_1=50, days_minus_2=-40)
        assert any(
            "tax_year - 2" in r and "outside 0-366" in r
            for r in updated.requires_human_review
        ), updated.requires_human_review

    def test_absurdly_large_prior_year_days_flagged(self):
        """Digit-duplication OCR error (e.g. '365' read twice as '365365')
        for a prior year — clearly impossible (>366 days in a year) but a
        very plausible OCR failure mode, and previously nothing caught it."""
        updated = self._run(days_current=120, days_minus_1=365365, days_minus_2=0)
        assert any(
            "tax_year - 1" in r and "outside 0-366" in r
            for r in updated.requires_human_review
        ), updated.requires_human_review

    def test_plausible_prior_year_days_not_flagged(self):
        """Sanity check: normal, in-range values from all three years must
        not be flagged (no false positives). Kept below the SPT resident
        threshold (120 + 30//3 + 30//6 = 135 < 183) so this exercises only
        the day-count bounds check, not the separate resident-alien-status
        flag."""
        updated = self._run(days_current=120, days_minus_1=30, days_minus_2=30)
        assert updated.requires_human_review == []


class TestL1StructuredOutputFailure:
    """When the LLM's structured-output call itself fails against garbled
    input (refusal, provider error, schema mismatch), safe_parse's primary
    invocation is unguarded (see src/agents/_llm_safety.py::safe_parse) —
    the raw exception propagates. Confirm it actually propagates rather
    than being swallowed into a fabricated "successful" result, and that
    the state is not left half-mutated / marked complete."""

    def test_primary_extraction_failure_propagates_and_state_not_marked_complete(self):
        client = MagicMock()
        client.beta.chat.completions.parse.side_effect = RuntimeError(
            "OCR text unparseable: model refused (contains no I-94 structure)"
        )
        agent = ResidencyAgent(llm_client=client)
        state = ReturnStateObject()

        with pytest.raises(RuntimeError):
            agent.process_residency(
                i94_ocr_text=GARBLED_OCR_TEXT,
                tax_year=2024,
                visa_type="F-1",
                first_us_arrival_year=2024,
                current_state=state,
            )
        assert "L1" not in state.completed_layers
        assert state.residency.days_present_current_year == 0  # untouched default

    def test_dual_extract_mismatch_on_garbled_input_raises_confidence_error(self):
        """A garbled I-94 scan is exactly the case where the primary and a
        second-opinion model would disagree wildly — that must surface as
        ExtractionConfidenceError, not resolve to one arbitrary answer."""
        primary = _client_returning(
            I94DayCountParams(days_current_year=300, days_minus_1=200, days_minus_2=100)
        )
        secondary = _client_returning(
            I94DayCountParams(days_current_year=30, days_minus_1=0, days_minus_2=0)
        )
        agent = ResidencyAgent(llm_client=primary, secondary_llm_client=secondary)
        state = ReturnStateObject()

        with pytest.raises(ExtractionConfidenceError) as excinfo:
            agent.process_residency(
                i94_ocr_text=GARBLED_OCR_TEXT,
                tax_year=2024,
                visa_type="H-1B",
                first_us_arrival_year=2020,
                current_state=state,
            )
        assert "days_current_year" in str(excinfo.value)
        assert "L1" not in state.completed_layers

    def test_secondary_call_itself_failing_on_garbled_input_raises_confidence_error(self):
        """If the second-opinion model can't parse the OCR text at all
        (e.g. times out on a huge noisy scan), that failure is itself a
        low-confidence signal per safe_parse's docstring — must raise, not
        silently fall back to the unverified primary result."""
        primary = _client_returning(
            I94DayCountParams(days_current_year=150, days_minus_1=0, days_minus_2=0)
        )
        secondary = MagicMock()
        secondary.beta.chat.completions.parse.side_effect = TimeoutError("provider timeout")
        agent = ResidencyAgent(llm_client=primary, secondary_llm_client=secondary)
        state = ReturnStateObject()

        with pytest.raises(ExtractionConfidenceError):
            agent.process_residency(
                i94_ocr_text=GARBLED_OCR_TEXT,
                tax_year=2024,
                visa_type="H-1B",
                first_us_arrival_year=2020,
                current_state=state,
            )


# ---------------------------------------------------------------------------
# L3 Income Agent — garbled/non-English/implausible W-2 & 1042-S extraction
# ---------------------------------------------------------------------------


class TestL3NonEnglishAndGarbledInputIsForwarded:
    def test_spanish_w2_text_forwarded_and_normal_response_not_flagged(self):
        client = _client_returning(
            W2Data(
                box_1_wages=18400.0,
                box_2_fed_withholding=1840.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_income(
            w2_ocr_texts=[NON_ENGLISH_SPANISH_W2_TEXT],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        call_kwargs = client.beta.chat.completions.parse.call_args.kwargs
        assert NON_ENGLISH_SPANISH_W2_TEXT in call_kwargs["messages"][1]["content"]
        assert updated.income.total_w2_wages == 18400.0
        validate_post_l3(updated)
        assert updated.requires_human_review == []

    def test_garbled_1042s_text_forwarded_verbatim(self):
        client = _client_returning(
            Form1042SData(
                box_1_income_code=16,
                box_2_gross_income=3000.0,
                box_3a_exemption_rate=14.0,
                box_3b_exemption_code="04",
                box_7a_fed_withheld=420.0,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_income(
            w2_ocr_texts=[],
            form_1042s_ocr_texts=[GARBLED_OCR_TEXT],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        call_kwargs = client.beta.chat.completions.parse.call_args.kwargs
        assert GARBLED_OCR_TEXT in call_kwargs["messages"][1]["content"]
        assert "L3" in updated.completed_layers


class TestL3NegativeWithholdingFix:
    """Regression coverage for the second gap found & fixed in this pass:
    a garbled OCR sign/decimal error on Box 2 (W-2) or Box 7a (1042-S) can
    produce a negative federal-withholding figure. Nothing previously
    checked for this — it would silently understate the amount already
    paid to the IRS (inflating the balance due or hiding a refund the
    filer is owed) with no human-review flag."""

    def test_negative_w2_federal_withholding_flagged(self):
        client = _client_returning(
            W2Data(
                box_1_wages=20000.0,
                box_2_fed_withholding=-4500.0,  # OCR misread a "(" as "-"
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_income(
            w2_ocr_texts=["garbled w2 text"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        assert updated.income.total_w2_withholding == -4500.0
        validate_post_l3(updated)
        assert any(
            "negative W-2 federal withholding" in r
            for r in updated.requires_human_review
        ), updated.requires_human_review

    def test_negative_1042s_federal_withholding_flagged(self):
        client = _client_returning(
            Form1042SData(
                box_1_income_code=16,
                box_2_gross_income=5000.0,
                box_3a_exemption_rate=14.0,
                box_3b_exemption_code="04",
                box_7a_fed_withheld=-700.0,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_income(
            w2_ocr_texts=[],
            form_1042s_ocr_texts=["garbled 1042-s text"],
            requires_services=False,
            is_qualified_expense=True,
            current_state=state,
        )
        assert updated.income.total_1042s_withholding == -700.0
        validate_post_l3(updated)
        assert any(
            "negative 1042-S federal withholding" in r
            for r in updated.requires_human_review
        ), updated.requires_human_review

    def test_plausible_withholding_not_flagged(self):
        client = _client_returning(
            W2Data(
                box_1_wages=20000.0,
                box_2_fed_withholding=2000.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_income(
            w2_ocr_texts=["clean w2 text"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        validate_post_l3(updated)
        assert updated.requires_human_review == []


class TestL3ImplausibleValuesAlreadyCaught:
    """Existing validator coverage exercised through the real mocked-LLM
    agent path (rather than by poking state.income directly), confirming
    the wiring actually reaches validate_post_l3 for OCR-plausible garble
    patterns beyond what test_orchestrator/test_validators.py covers in
    isolation."""

    def test_digit_duplication_wages_flagged(self):
        """A very plausible OCR failure: '$32,500.00' misread with a
        duplicated/shifted run of digits into something absurd."""
        client = _client_returning(
            W2Data(
                box_1_wages=325_000_000.0,
                box_2_fed_withholding=4875.0,
                box_4_ss_withheld=2015.0,
                box_6_medicare_withheld=471.25,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_income(
            w2_ocr_texts=["garbled w2 text with smeared digits"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=state,
        )
        validate_post_l3(updated)
        assert any(
            "reasonability ceiling" in r for r in updated.requires_human_review
        ), updated.requires_human_review

    def test_negative_1042s_gross_income_flagged(self):
        client = _client_returning(
            Form1042SData(
                box_1_income_code=16,
                box_2_gross_income=-5000.0,
                box_3a_exemption_rate=14.0,
                box_3b_exemption_code="04",
                box_7a_fed_withheld=0.0,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        updated = agent.process_income(
            w2_ocr_texts=[],
            form_1042s_ocr_texts=["garbled 1042-s text"],
            requires_services=False,
            is_qualified_expense=True,
            current_state=state,
        )
        validate_post_l3(updated)
        assert any(
            "negative 1042-S gross" in r for r in updated.requires_human_review
        ), updated.requires_human_review


class TestL3StructuredOutputFailure:
    def test_primary_extraction_failure_propagates_and_l3_not_marked_complete(self):
        """A W-2 scan so garbled the model can't produce structured output
        at all must fail loudly, not be swallowed into a $0 W-2."""
        client = MagicMock()
        client.beta.chat.completions.parse.side_effect = ValueError(
            "could not produce structured output for this input"
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        with pytest.raises(ValueError):
            agent.process_income(
                w2_ocr_texts=[GARBLED_OCR_TEXT],
                form_1042s_ocr_texts=[],
                requires_services=False,
                is_qualified_expense=False,
                current_state=state,
            )
        assert "L3" not in state.completed_layers
        assert state.income.total_w2_wages == 0.0

    def test_unknown_income_code_from_garbled_1042s_raises_and_is_not_swallowed(self):
        """Box 1 income code misread by OCR into a value IRS never issues
        (e.g. '99' from a smeared '19') must raise, not silently get
        routed as if it were a known ECI/FDAP/EXCLUDED code."""
        client = _client_returning(
            Form1042SData(
                box_1_income_code=99,
                box_2_gross_income=4000.0,
                box_3a_exemption_rate=0.0,
                box_3b_exemption_code="00",
                box_7a_fed_withheld=0.0,
            )
        )
        agent = IncomeAgent(llm_client=client)
        state = ReturnStateObject()

        with pytest.raises(ValueError, match="Unknown or unsupported"):
            agent.process_income(
                w2_ocr_texts=[],
                form_1042s_ocr_texts=["garbled 1042-s with smeared income code"],
                requires_services=False,
                is_qualified_expense=False,
                current_state=state,
            )
        assert "L3" not in state.completed_layers

    def test_dual_extract_mismatch_on_garbled_w2_raises_confidence_error(self):
        primary = _client_returning(
            W2Data(
                box_1_wages=32000.0,
                box_2_fed_withholding=3200.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )
        secondary = _client_returning(
            W2Data(
                box_1_wages=3200.0,  # OCR ate a zero on the second pass
                box_2_fed_withholding=3200.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )
        agent = IncomeAgent(llm_client=primary, secondary_llm_client=secondary)
        state = ReturnStateObject()

        with pytest.raises(ExtractionConfidenceError) as excinfo:
            agent.process_income(
                w2_ocr_texts=[GARBLED_OCR_TEXT],
                form_1042s_ocr_texts=[],
                requires_services=False,
                is_qualified_expense=False,
                current_state=state,
            )
        assert "box_1_wages" in str(excinfo.value)
        assert "L3" not in state.completed_layers
