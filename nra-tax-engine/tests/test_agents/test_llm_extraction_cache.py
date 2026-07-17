"""Tests for the in-process LLM/OCR extraction cache (src/agents/_llm_cache.py).

Proves, for each of the three LLM-calling layers (L1 residency, L3 income,
L4 treaty):

    (a) An identical repeated call does NOT invoke the LLM client a second
        time -- the cached result is reused instead.
    (b) A genuinely different input (different document text, or a
        different tax_year for L1) DOES invoke the LLM client again.

The cache is process-wide (module-level), shared across agent instances --
not per-instance -- so each test below deliberately wires TWO separate
agent instances to TWO separate mock clients with clearly different fake
responses. That way, "the LLM was not called again" and "the state reflects
the cached value, not the second client's own mock" are both provable: if
caching were broken (or merely per-instance), the second agent would call
its own mock and the assertions on the resulting state would fail.

``tests/conftest.py`` clears these module-level caches before and after
every test, so tests here don't need to manage that themselves.
"""

from unittest.mock import MagicMock

from src.agents._llm_cache import LLMExtractionCache
from src.agents.l1_residency import I94DayCountParams, ResidencyAgent
from src.agents.l3_income import IncomeAgent, W2Data
from src.agents.l4_treaty import TreatyAgent, TreatyCategoryMapping
from src.orchestrator.state import ReturnStateObject


def _client_returning(parsed):
    """Build a mock OpenAI-compatible client whose .parse() returns ``parsed``."""
    client = MagicMock()
    completion = MagicMock()
    completion.choices = [MagicMock()]
    completion.choices[0].message.parsed = parsed
    client.beta.chat.completions.parse.return_value = completion
    return client


class TestLLMExtractionCacheUtility:
    """Direct tests of the small cache primitive itself."""

    def test_make_key_is_stable_for_the_same_inputs(self):
        assert LLMExtractionCache.make_key("a", 1) == LLMExtractionCache.make_key("a", 1)

    def test_make_key_is_order_sensitive(self):
        # Guards against "ab"+"c" colliding with "a"+"bc" style bugs.
        assert LLMExtractionCache.make_key("a", "b") != LLMExtractionCache.make_key("ab")

    def test_get_or_call_computes_once_then_reuses(self):
        cache = LLMExtractionCache()
        calls = []

        def compute():
            calls.append(1)
            return "computed-value"

        key = cache.make_key("same-input")
        assert cache.get_or_call(key, compute) == "computed-value"
        assert cache.get_or_call(key, compute) == "computed-value"
        assert len(calls) == 1

    def test_get_or_call_recomputes_for_a_different_key(self):
        cache = LLMExtractionCache()
        calls = []

        def compute():
            calls.append(1)
            return len(calls)

        assert cache.get_or_call(cache.make_key("one"), compute) == 1
        assert cache.get_or_call(cache.make_key("two"), compute) == 2
        assert len(calls) == 2

    def test_clear_forces_recomputation(self):
        cache = LLMExtractionCache()
        calls = []

        def compute():
            calls.append(1)
            return len(calls)

        key = cache.make_key("x")
        assert cache.get_or_call(key, compute) == 1
        cache.clear()
        assert cache.get_or_call(key, compute) == 2


class TestL1ResidencyCaching:
    def _base_kwargs(self, **overrides):
        kwargs = dict(
            i94_ocr_text="SAME I-94 TEXT",
            tax_year=2024,
            visa_type="F-1",
            first_us_arrival_year=2022,
        )
        kwargs.update(overrides)
        return kwargs

    def test_identical_i94_text_and_tax_year_skips_second_llm_call(self):
        client_a = _client_returning(
            I94DayCountParams(days_current_year=300, days_minus_1=365, days_minus_2=365)
        )
        client_b = _client_returning(
            I94DayCountParams(days_current_year=1, days_minus_1=1, days_minus_2=1)
        )

        ResidencyAgent(llm_client=client_a).process_residency(
            current_state=ReturnStateObject(), **self._base_kwargs()
        )
        assert client_a.beta.chat.completions.parse.call_count == 1

        updated_b = ResidencyAgent(llm_client=client_b).process_residency(
            current_state=ReturnStateObject(), **self._base_kwargs()
        )

        # client_b's own mock is never touched -- the cached result from
        # client_a's identical call satisfies this request instead.
        assert client_b.beta.chat.completions.parse.call_count == 0
        assert updated_b.residency.days_present_current_year == 300

    def test_different_tax_year_still_invokes_llm(self):
        client_a = _client_returning(
            I94DayCountParams(days_current_year=300, days_minus_1=365, days_minus_2=365)
        )
        client_b = _client_returning(
            I94DayCountParams(days_current_year=10, days_minus_1=10, days_minus_2=10)
        )

        ResidencyAgent(llm_client=client_a).process_residency(
            current_state=ReturnStateObject(), **self._base_kwargs()
        )
        updated_b = ResidencyAgent(llm_client=client_b).process_residency(
            current_state=ReturnStateObject(), **self._base_kwargs(tax_year=2023)
        )

        assert client_b.beta.chat.completions.parse.call_count == 1
        assert updated_b.residency.days_present_current_year == 10

    def test_different_i94_text_still_invokes_llm(self):
        client_a = _client_returning(
            I94DayCountParams(days_current_year=300, days_minus_1=365, days_minus_2=365)
        )
        client_b = _client_returning(
            I94DayCountParams(days_current_year=20, days_minus_1=20, days_minus_2=20)
        )

        ResidencyAgent(llm_client=client_a).process_residency(
            current_state=ReturnStateObject(), **self._base_kwargs(i94_ocr_text="I-94 TEXT ONE")
        )
        updated_b = ResidencyAgent(llm_client=client_b).process_residency(
            current_state=ReturnStateObject(), **self._base_kwargs(i94_ocr_text="I-94 TEXT TWO")
        )

        assert client_b.beta.chat.completions.parse.call_count == 1
        assert updated_b.residency.days_present_current_year == 20


class TestL3IncomeCaching:
    def test_identical_w2_text_skips_second_llm_call(self):
        client_a = _client_returning(
            W2Data(
                box_1_wages=15000.0,
                box_2_fed_withholding=1500.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )
        client_b = _client_returning(
            W2Data(
                box_1_wages=999.0,
                box_2_fed_withholding=1.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )

        IncomeAgent(llm_client=client_a).process_income(
            w2_ocr_texts=["SAME W-2 TEXT"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=ReturnStateObject(),
        )
        assert client_a.beta.chat.completions.parse.call_count == 1

        updated_b = IncomeAgent(llm_client=client_b).process_income(
            w2_ocr_texts=["SAME W-2 TEXT"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=ReturnStateObject(),
        )

        assert client_b.beta.chat.completions.parse.call_count == 0
        assert updated_b.income.total_w2_wages == 15000.0

    def test_different_w2_text_still_invokes_llm(self):
        client_a = _client_returning(
            W2Data(
                box_1_wages=15000.0,
                box_2_fed_withholding=1500.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )
        client_b = _client_returning(
            W2Data(
                box_1_wages=42.0,
                box_2_fed_withholding=1.0,
                box_4_ss_withheld=0.0,
                box_6_medicare_withheld=0.0,
            )
        )

        IncomeAgent(llm_client=client_a).process_income(
            w2_ocr_texts=["W-2 TEXT ONE"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=ReturnStateObject(),
        )
        updated_b = IncomeAgent(llm_client=client_b).process_income(
            w2_ocr_texts=["W-2 TEXT TWO"],
            form_1042s_ocr_texts=[],
            requires_services=False,
            is_qualified_expense=False,
            current_state=ReturnStateObject(),
        )

        assert client_b.beta.chat.completions.parse.call_count == 1
        assert updated_b.income.total_w2_wages == 42.0


class TestL4TreatyCaching:
    @staticmethod
    def _state(**overrides):
        state = ReturnStateObject()
        state.residency.status = "nonresident_alien"
        state.residency.exempt_visa_type = "J-1"
        state.residency.years_in_exempt_status = 2
        state.income.eci_taxable_total = 30000.0
        for key, value in overrides.items():
            setattr(state.residency, key, value)
        return state

    def test_identical_income_description_skips_second_llm_call(self):
        client_a = _client_returning(TreatyCategoryMapping(mapped_category="teaching_research"))
        client_b = _client_returning(
            TreatyCategoryMapping(mapped_category="student_personal_services")
        )

        TreatyAgent(llm_client=client_a).process_treaties(
            tax_residence_country="China",
            income_description="SAME DESCRIPTION",
            current_state=self._state(),
        )
        assert client_a.beta.chat.completions.parse.call_count == 1

        updated_b = TreatyAgent(llm_client=client_b).process_treaties(
            tax_residence_country="China",
            income_description="SAME DESCRIPTION",
            current_state=self._state(),
        )

        assert client_b.beta.chat.completions.parse.call_count == 0
        # Article 19 (teaching/research) is what the cached classification
        # drives -- client_b's own (never-invoked) "student" mock would
        # have routed to a different article entirely.
        assert updated_b.treaty.article_number == "19"

    def test_different_income_description_still_invokes_llm(self):
        client_a = _client_returning(TreatyCategoryMapping(mapped_category="teaching_research"))
        client_b = _client_returning(
            TreatyCategoryMapping(mapped_category="student_personal_services")
        )

        TreatyAgent(llm_client=client_a).process_treaties(
            tax_residence_country="China",
            income_description="Visiting researcher at MIT",
            current_state=self._state(),
        )
        updated_b = TreatyAgent(llm_client=client_b).process_treaties(
            tax_residence_country="China",
            income_description="On-campus dining hall worker",
            current_state=self._state(exempt_visa_type="F-1"),
        )

        assert client_b.beta.chat.completions.parse.call_count == 1
        assert updated_b.treaty.article_number == "20(c)"
