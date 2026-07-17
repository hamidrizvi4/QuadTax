"""L4 Treaty Agent — maps income descriptions to treaty categories.

The agent has two responsibilities:

1. Use the LLM as a *classifier* — turn the filer's free-text income description
   (e.g. "PhD teaching assistant", "research stipend", "campus barista") into
   one of the closed-set treaty categories defined in
   :data:`~src.functions.treaty_schema.TreatyCategory`.
2. Hand the classification + income totals to the deterministic
   :class:`~src.functions.treaty_evaluator.TreatyEvaluator`, which iterates
   every applicable article for the country and returns a list of
   :class:`~src.functions.treaty_schema.AppliedTreatyBenefit` objects.

The agent does NOT decide which articles apply, which year caps bite, or
what amounts are exempt — those are deterministic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from src.agents._llm_cache import LLMExtractionCache
from src.agents._llm_safety import safe_parse
from src.functions.treaty_evaluator import TreatyEvaluator
from src.functions.treaty_schema import AppliedTreatyBenefit, TreatyCategory
from src.llm_config import PRIMARY_MODEL, SECONDARY_MODEL, get_openai_client

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


# Process-lifetime cache for income-description -> treaty-category
# classification. The classifier prompt is static and the result depends
# only on the filer's free-text income description, so that text alone is
# the deterministic key.
_treaty_classification_cache = LLMExtractionCache()


# Category enum exposed to the LLM. Mirrors :data:`TreatyCategory` minus the
# states we never expect the model to produce (e.g. "pension_annuity" for a
# student-focused intake flow). Re-exported here so we can evolve the LLM
# enum independently of the database schema if needed.
LLMTreatyCategory = Literal[
    "scholarship_fellowship",
    "student_personal_services",
    "apprentice_trainee",
    "teaching_research",
    "independent_personal_services",
    "dependent_personal_services",
    "foreign_source_remittance",
    "none",
]


class TreatyCategoryMapping(BaseModel):
    """Schema forcing the LLM to emit a single valid treaty category."""

    mapped_category: LLMTreatyCategory = Field(
        description=(
            "The closed-set treaty category that best matches the filer's income "
            "description. Use 'student_personal_services' for student wages, "
            "'teaching_research' for visiting professors/researchers, "
            "'scholarship_fellowship' for fellowship/stipend grants, "
            "'foreign_source_remittance' when the support comes from outside the US, "
            "and 'none' when no treaty category fits."
        )
    )


class TreatyAgent:
    """LLM-powered classifier + deterministic treaty applicator."""

    def __init__(self, llm_client: Any = None, secondary_llm_client: Any = None):
        if llm_client is None:
            self.llm_client = get_openai_client()
        else:
            self.llm_client = llm_client
        self.secondary_llm_client = secondary_llm_client

    # ------------------------------------------------------------------
    # LLM classification
    # ------------------------------------------------------------------

    def _classify_income_description(self, income_description: str) -> LLMTreatyCategory:
        system_prompt = (
            "You are a tax-treaty classifier for the IRS Form 1040-NR. "
            "Pick exactly one category from the closed set. "
            "Use 'student_personal_services' for wages a student earns from US sources. "
            "Use 'teaching_research' for visiting professors/researchers. "
            "Use 'scholarship_fellowship' for fellowship or scholarship grant income. "
            "Use 'foreign_source_remittance' when the income comes from outside the US. "
            "Return 'none' if no treaty category fits."
        )
        cache_key = _treaty_classification_cache.make_key(income_description)

        def _call() -> LLMTreatyCategory:
            result = safe_parse(
                primary_client=self.llm_client,
                primary_model=PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Income description:\n{income_description}"},
                ],
                response_format=TreatyCategoryMapping,
                secondary_client=self.secondary_llm_client,
                secondary_model=SECONDARY_MODEL if self.secondary_llm_client else None,
            )
            return result.mapped_category

        return _treaty_classification_cache.get_or_call(cache_key, _call)

    # ------------------------------------------------------------------
    # State mutation
    # ------------------------------------------------------------------

    def _gross_by_category(
        self,
        primary_category: LLMTreatyCategory,
        current_state: "ReturnStateObject",
    ) -> Dict[TreatyCategory, float]:
        """Build the per-category gross-income dict the evaluator consumes.

        The L4 agent maps the LLM's primary category to the matching gross
        bucket on ``IncomeState``. ECI buckets are used for compensation-type
        categories (student wages, teaching/research); FDAP for scholarship.
        """
        gross: Dict[TreatyCategory, float] = {}
        income = current_state.income

        if primary_category == "student_personal_services":
            gross["student_personal_services"] = income.eci_taxable_total
        elif primary_category == "teaching_research":
            gross["teaching_research"] = income.eci_taxable_total
        elif primary_category in {"independent_personal_services", "dependent_personal_services"}:
            gross[primary_category] = income.eci_taxable_total  # type: ignore[index]
        elif primary_category == "scholarship_fellowship":
            # Scholarship is typically routed to FDAP unless services are required.
            gross["scholarship_fellowship"] = (
                income.fdap_taxable_total + income.exempt_scholarship_total
            )
        elif primary_category == "foreign_source_remittance":
            gross["foreign_source_remittance"] = (
                income.eci_taxable_total + income.fdap_taxable_total
            )
        elif primary_category == "apprentice_trainee":
            gross["apprentice_trainee"] = income.eci_taxable_total
        return gross

    def _is_us_source_map(
        self,
        primary_category: LLMTreatyCategory,
    ) -> Dict[TreatyCategory, Optional[bool]]:
        if primary_category == "foreign_source_remittance":
            return {"foreign_source_remittance": False}
        # Student wages / teaching from a US employer are US-source.
        if primary_category in {
            "student_personal_services",
            "teaching_research",
            "dependent_personal_services",
            "independent_personal_services",
            "apprentice_trainee",
        }:
            return {primary_category: True}  # type: ignore[dict-item]
        # Scholarship source depends; leave unset so the evaluator does not filter.
        return {}

    def process_treaties(
        self,
        tax_residence_country: str,
        income_description: str,
        current_state: "ReturnStateObject",
    ) -> "ReturnStateObject":
        """Classify the filer's income and apply every matching treaty article.

        Args:
            tax_residence_country: ISO2 code (preferred) or country name. Country
                names map to ISO2 via a hand-maintained alias map.
            income_description: Free-text description of the filer's primary income.
            current_state: Mutable :class:`ReturnStateObject`.

        Returns:
            ``current_state`` with ``TreatyState`` mutated and ``L4`` marked complete.
            Resident aliens short-circuit and the layer is marked ``L4_Skipped``
            unless an article carries the saving-clause exception (then the
            evaluator still runs).
        """
        evaluator = TreatyEvaluator(tax_year=current_state.tax_year)
        iso2 = _resolve_country_to_iso2(tax_residence_country)

        # Resident aliens: only run the evaluator when the country has at least
        # one saving-clause-exception article. Otherwise short-circuit.
        if current_state.residency.status == "resident_alien":
            country_doc = evaluator.country(iso2) if iso2 else None
            has_exception = bool(
                country_doc
                and any(a.saving_clause_exception for a in country_doc.articles)
            )
            if not has_exception:
                current_state.mark_layer_complete("L4_Skipped")
                return current_state

        if iso2 is None:
            current_state.mark_layer_complete("L4_Skipped")
            return current_state

        primary_category = self._classify_income_description(income_description)
        if primary_category == "none":
            current_state.mark_layer_complete("L4")
            return current_state

        gross_by_category = self._gross_by_category(primary_category, current_state)
        is_us_source_by_category = self._is_us_source_map(primary_category)

        benefits = evaluator.evaluate(
            country=iso2,
            visa_type=current_state.residency.exempt_visa_type or "F-1",
            residency_status=current_state.residency.status,
            years_since_arrival=current_state.residency.years_in_exempt_status,
            gross_by_category=gross_by_category,
            is_us_source_by_category=is_us_source_by_category,
        )

        self._mutate_state(current_state, iso2, benefits)
        current_state.mark_layer_complete("L4")
        return current_state

    @staticmethod
    def _mutate_state(
        state: "ReturnStateObject",
        iso2: str,
        benefits: list[AppliedTreatyBenefit],
    ) -> None:
        state.treaty.applied_benefits = [b.model_dump() for b in benefits]
        state.treaty.country = iso2
        if not benefits:
            state.treaty.is_eligible = False
            state.treaty.article_number = None
            state.treaty.exempt_amount_applied = 0.0
            state.treaty.applied_to_category = None
            state.treaty.requires_form_8833 = False
            return

        primary = max(benefits, key=lambda b: b.exempt_amount)
        any_8833 = any(b.requires_form_8833 for b in benefits)

        # ``exempt_amount_applied`` is the total income EXEMPTED by treaty (drives
        # 1040-NR line 1k and Schedule OI Item L). India Article 21(2) is a
        # standard-DEDUCTION equivalent, not an income exemption — it must NOT
        # be summed here or it would wrongly appear as exempt wages on the form.
        total = sum(
            b.exempt_amount
            for b in benefits
            if not _is_india_standard_deduction(b)
        )

        state.treaty.is_eligible = True
        state.treaty.article_number = primary.article_id
        state.treaty.exempt_amount_applied = total
        state.treaty.applied_to_category = primary.category
        state.treaty.requires_form_8833 = any_8833

        if any_8833 and "8833" not in state.forms_required:
            state.forms_required.append("8833")


def _is_india_standard_deduction(benefit: AppliedTreatyBenefit) -> bool:
    """True for the India Art 21(2) benefit — a deduction, not an income exemption."""
    return benefit.country_iso2 == "IN" and benefit.article_id == "21(2)"


# ---------------------------------------------------------------------------
# Country name → ISO2 alias resolver
# ---------------------------------------------------------------------------

# A pragmatic hand-maintained map. The Pub-901-derived treaties database keys
# on ISO2. The intake form may emit either a name or an ISO2. We accept either.
_NAME_TO_ISO2: Dict[str, str] = {
    "china": "CN",
    "china (people's republic of)": "CN",
    "prc": "CN",
    "india": "IN",
    "korea": "KR",
    "korea, republic of": "KR",
    "south korea": "KR",
    "germany": "DE",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "canada": "CA",
    "pakistan": "PK",
    "japan": "JP",
    "mexico": "MX",
    "spain": "ES",
    "france": "FR",
    "indonesia": "ID",
    "netherlands": "NL",
    "bangladesh": "BD",
    "belgium": "BE",
    "bulgaria": "BG",
    "cyprus": "CY",
    "czech republic": "CZ",
    "czechia": "CZ",
    "denmark": "DK",
    "egypt": "EG",
    "estonia": "EE",
    "greece": "GR",
    "iceland": "IS",
    "israel": "IL",
    "jamaica": "JM",
    "kazakhstan": "KZ",
    "latvia": "LV",
    "lithuania": "LT",
    "morocco": "MA",
    "malta": "MT",
    "norway": "NO",
    "philippines": "PH",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "slovakia": "SK",
    "slovak republic": "SK",
    "slovenia": "SI",
    "sri lanka": "LK",
    "thailand": "TH",
    "trinidad and tobago": "TT",
    "trinidad": "TT",
    "tunisia": "TN",
    "ukraine": "UA",
    "venezuela": "VE",
    "australia": "AU",
    "austria": "AT",
    "switzerland": "CH",
    "finland": "FI",
    "ireland": "IE",
    "italy": "IT",
    "luxembourg": "LU",
    "new zealand": "NZ",
    "sweden": "SE",
    "turkey": "TR",
    "south africa": "ZA",
    "barbados": "BB",
    "armenia": "AM",
    "azerbaijan": "AZ",
    "belarus": "BY",
    "georgia": "GE",
    "kyrgyzstan": "KG",
    "moldova": "MD",
    "tajikistan": "TJ",
    "turkmenistan": "TM",
    "uzbekistan": "UZ",
    "hungary": "HU",
    "russia": "RU",
    "russian federation": "RU",
}


def _resolve_country_to_iso2(country: str) -> Optional[str]:
    """Return an ISO2 code for ``country`` or None if unknown."""
    if not country:
        return None
    if len(country) == 2 and country.isalpha():
        return country.upper()
    return _NAME_TO_ISO2.get(country.strip().lower())
