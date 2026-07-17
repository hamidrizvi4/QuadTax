"""L3 Income Agent — Classifies and categorizes income sources.

Extracts strict box values from W-2, 1042-S, and 1099-* documents via an LLM
operating in structured-output mode, then hands those typed values to the
deterministic :class:`IncomeCodeMapper` and :class:`WithholdingReconciler`.

Phase 2 changes:
    * Added 1099-INT / 1099-DIV / 1099-B / 1099-MISC parsing.
    * Withholding totals are now computed by :func:`reconcile` and stored
      on ``IncomeState`` for downstream consumption.
    * 1042-S parsing captures the chapter indicator (Ch 3 vs Ch 4).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.agents._llm_cache import LLMExtractionCache
from src.agents._llm_safety import safe_parse
from src.functions.code_mapper import IncomeCodeMapper
from src.functions.withholding_reconciler import (
    Form1042SEntry,
    Form1099Entry,
    W2Entry,
    reconcile,
)
from src.llm_config import PRIMARY_MODEL, SECONDARY_MODEL, get_openai_client

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


# Process-lifetime cache shared by every document-extraction call this agent
# makes (W-2, 1042-S, 1099-*). None of these extractions depend on tax_year
# or any other agent parameter -- box values on a given document are the
# same regardless of which return they're being filed for -- so the cache
# key is the schema name (to keep W-2/1042-S/1099 calls from colliding with
# each other even if two OCR blobs coincidentally matched) plus the exact
# system prompt and OCR text.
_extraction_cache = LLMExtractionCache()


class W2Data(BaseModel):
    """W-2 box values used by the engine."""

    box_1_wages: float = Field(description="Box 1: Wages, tips, other compensation")
    box_2_fed_withholding: float = Field(description="Box 2: Federal income tax withheld")
    box_3_ss_wages: float = Field(default=0.0, description="Box 3: Social Security wages")
    box_4_ss_withheld: float = Field(description="Box 4: Social Security tax withheld")
    box_5_medicare_wages: float = Field(default=0.0, description="Box 5: Medicare wages and tips")
    box_6_medicare_withheld: float = Field(description="Box 6: Medicare tax withheld")
    box_17_state_income_tax: float = Field(default=0.0, description="Box 17: State income tax")
    box_18_local_wages: float = Field(default=0.0, description="Box 18: Local wages, tips, etc.")
    box_19_local_income_tax: float = Field(default=0.0, description="Box 19: Local income tax")
    box_20_locality_name: str = Field(default="", description="Box 20: Locality name (e.g., NYC)")


class Form1042SData(BaseModel):
    """1042-S box values used by the engine."""

    box_1_income_code: int = Field(description="Box 1: Income code (2-digit integer)")
    box_2_gross_income: float = Field(description="Box 2: Gross income")
    box_3a_exemption_rate: float = Field(description="Box 3a: Exemption Code/Rate")
    box_3b_exemption_code: str = Field(description="Box 3b: Exemption Code")
    box_7a_fed_withheld: float = Field(description="Box 7a: Federal tax withheld")
    chapter_indicator: int = Field(
        default=3,
        description="Box 3 chapter indicator: 3 = NRA withholding, 4 = FATCA.",
    )


class Form1099Data(BaseModel):
    """Generic 1099-{INT,DIV,B,MISC} extraction."""

    form_kind: Literal["INT", "DIV", "B", "MISC"]
    gross_amount: float = Field(default=0.0)
    fed_withholding: float = Field(default=0.0, description="Federal income tax withheld (box 4).")


class IncomeAgent:
    """LLM-powered agent for income classification."""

    def __init__(self, llm_client: Any = None, secondary_llm_client: Any = None):
        if llm_client is None:
            self.llm_client = get_openai_client()
        else:
            self.llm_client = llm_client
        self.secondary_llm_client = secondary_llm_client

    def _parse(self, schema, system_prompt: str, user_text: str):
        cache_key = _extraction_cache.make_key(schema.__name__, system_prompt, user_text)
        return _extraction_cache.get_or_call(
            cache_key,
            lambda: safe_parse(
                primary_client=self.llm_client,
                primary_model=PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                response_format=schema,
                secondary_client=self.secondary_llm_client,
                secondary_model=SECONDARY_MODEL if self.secondary_llm_client else None,
            ),
        )

    def _parse_many(self, schema, system_prompt: str, texts: List[str]) -> List[Any]:
        """Run :meth:`_parse` for every document in ``texts`` concurrently.

        Each document's extraction is independent (no document's LLM call
        depends on another's result), so this fans the per-document
        ``self._parse`` calls out across a thread pool instead of the
        original strictly-sequential ``for`` loop. The underlying OpenAI
        client is synchronous, so threads (not asyncio) are the fit here.

        Behavior is preserved exactly relative to the old sequential loop:

        * Return order always matches ``texts`` order (``executor.map``
          yields results in submission order regardless of completion
          order), so callers that zip results back against their source
          documents by index see no change.
        * Fail-fast semantics are preserved: if any document's extraction
          raises (e.g. ``ExtractionConfidenceError`` from the dual-extract
          cross-check in ``_llm_safety.safe_parse``), that exception
          propagates out of this call and no result list is returned --
          the caller never sees a partial/mixed set of successes, exactly
          as the old loop would abort on the first failing iteration
          rather than continuing with what succeeded. The one difference
          from the old loop is that, on failure, extraction for the
          *other* documents in the same batch may already have been
          kicked off (since they run concurrently rather than not being
          reached yet) -- the externally visible outcome ("fail the whole
          request") is identical.
        """
        if not texts:
            return []
        if len(texts) == 1:
            # Skip the thread-pool overhead; also keeps single-document
            # behavior byte-for-byte identical to before this change.
            return [self._parse(schema, system_prompt, texts[0])]
        with ThreadPoolExecutor(max_workers=len(texts)) as executor:
            return list(
                executor.map(lambda t: self._parse(schema, system_prompt, t), texts)
            )

    def process_income(
        self,
        w2_ocr_texts: List[str],
        form_1042s_ocr_texts: List[str],
        requires_services: bool,
        is_qualified_expense: bool,
        current_state: "ReturnStateObject",
        form_1099_ocr_texts: Optional[List[str]] = None,
    ) -> "ReturnStateObject":
        """Parse documents, route 1042-S to ECI/FDAP/EXCLUDED, reconcile withholding."""
        form_1099_ocr_texts = form_1099_ocr_texts or []

        # Each of these three extraction passes loops over N independent
        # documents of the same kind (N W-2s, N 1042-S's, N 1099s). No
        # document's LLM extraction depends on another's result, so
        # _parse_many fans the per-document calls out across a thread pool
        # rather than making them one-at-a-time. The three passes themselves
        # still run in sequence (W-2s, then 1042-S's, then 1099s) since that
        # ordering was never the bottleneck and preserving it keeps this
        # change minimal.
        parsed_w2s: List[W2Data] = self._parse_many(
            W2Data,
            "You are a precise W-2 OCR parser. Extract the requested fields.",
            [f"W-2 OCR Text:\n{w2_text}" for w2_text in w2_ocr_texts],
        )

        parsed_1042s: List[Form1042SData] = self._parse_many(
            Form1042SData,
            "You are a precise 1042-S OCR parser. Extract the requested fields. "
            "Chapter indicator: return 3 for standard NRA withholding, 4 for FATCA.",
            [f"1042-S OCR Text:\n{f_text}" for f_text in form_1042s_ocr_texts],
        )

        parsed_1099s: List[Form1099Data] = self._parse_many(
            Form1099Data,
            "You are a precise 1099 OCR parser. Identify the form kind "
            "(INT/DIV/B/MISC) and extract the gross amount and box 4 "
            "federal income tax withheld.",
            [f"1099 OCR Text:\n{f_text}" for f_text in form_1099_ocr_texts],
        )

        # --- W-2 aggregation ----------------------------------------------
        total_w2_wages = sum(w2.box_1_wages for w2 in parsed_w2s)

        # --- 1042-S routing -----------------------------------------------
        mapper = IncomeCodeMapper()
        total_1042s_gross = 0.0
        routed_eci = 0.0
        routed_fdap = 0.0
        routed_excluded = 0.0

        for entry in parsed_1042s:
            total_1042s_gross += entry.box_2_gross_income
            result = mapper.route_1042s_income(
                income_code=entry.box_1_income_code,
                gross_amount=entry.box_2_gross_income,
                requires_services=requires_services,
                is_qualified_expense=is_qualified_expense,
            )
            amount = result["taxable_amount"]
            if result["category"] == "ECI":
                routed_eci += amount
            elif result["category"] == "FDAP":
                routed_fdap += amount
            elif result["category"] == "EXCLUDED":
                routed_excluded += amount

        # --- Withholding reconciliation -----------------------------------
        report = reconcile(
            w2s=[
                W2Entry(
                    box_1_wages=w.box_1_wages,
                    box_2_fed_withholding=w.box_2_fed_withholding,
                    box_4_ss_withheld=w.box_4_ss_withheld,
                    box_6_medicare_withheld=w.box_6_medicare_withheld,
                    box_17_state_income_tax=w.box_17_state_income_tax,
                    box_19_local_income_tax=w.box_19_local_income_tax,
                    box_18_local_wages=w.box_18_local_wages,
                    box_20_locality_name=w.box_20_locality_name,
                )
                for w in parsed_w2s
            ],
            f1042s=[
                Form1042SEntry(
                    box_1_income_code=e.box_1_income_code,
                    box_2_gross_income=e.box_2_gross_income,
                    box_7a_fed_withheld=e.box_7a_fed_withheld,
                    chapter_indicator=e.chapter_indicator,
                )
                for e in parsed_1042s
            ],
            f1099s=[
                Form1099Entry(
                    form_kind=e.form_kind,
                    gross_amount=e.gross_amount,
                    fed_withholding=e.fed_withholding,
                )
                for e in parsed_1099s
            ],
            estimated_payments=(
                [current_state.extras.estimated_federal_payment_amount]
                if current_state.extras.made_estimated_federal_payments
                else []
            ),
        )

        # --- State mutation ----------------------------------------------
        current_state.income.total_w2_wages = total_w2_wages
        current_state.income.total_1042s_gross = total_1042s_gross
        current_state.income.eci_taxable_total = total_w2_wages + routed_eci
        current_state.income.fdap_taxable_total = routed_fdap
        current_state.income.exempt_scholarship_total = routed_excluded

        current_state.income.total_w2_withholding = float(report.federal_w2)
        current_state.income.total_1042s_withholding = float(
            report.federal_1042s_ch3 + report.federal_1042s_ch4
        )
        current_state.income.raw_ss_withheld = float(report.ss_withheld_w2)
        current_state.income.raw_medicare_withheld = float(report.medicare_withheld_w2)

        # Expose the full reconciliation report on the state for later layers.
        current_state.withholding_report = report.to_dict_floats()

        current_state.mark_layer_complete("L3")
        return current_state
