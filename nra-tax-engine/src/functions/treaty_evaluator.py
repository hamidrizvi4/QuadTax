# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Treaty evaluator — applies the per-country article rules deterministically.

This module replaces the previous flat 2-country lookup. It loads the
per-country JSON files seeded under ``database/tax_year/<year>/treaties/``,
validates each through the :mod:`treaty_schema` Pydantic models, and exposes
:meth:`TreatyEvaluator.evaluate` which returns every applicable
:class:`AppliedTreatyBenefit` for a given filer's circumstances.

The evaluator handles:
    * Multi-article countries (China, India, Korea, etc.).
    * Per-article saving-clause exceptions — a benefit may survive transition
      from NRA to resident-alien status.
    * Source restrictions — ``us_source_only`` / ``foreign_source_only`` /
      ``any_source``.
    * Dollar caps (capped per year) and year caps (window from arrival).
    * Visa-type filtering (e.g. ``F-1`` student articles do not apply to
      ``J-1`` researchers).
    * Form 8833 disclosure triggers per article, with Notice 2010-21 exception.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.functions.treaty_schema import (
    AppliedTreatyBenefit,
    TreatyArticle,
    TreatyCategory,
    TreatyDocument,
)

logger = logging.getLogger(__name__)


class TreatyEvaluator:
    """Loads per-country treaty JSONs and applies them to filer income."""

    def __init__(
        self,
        tax_year: int = 2025,
        treaties_dir: Union[str, Path, None] = None,
    ) -> None:
        """Initialize the evaluator and load every country file under the year directory.

        Args:
            tax_year: Calendar year of the return (default 2025).
            treaties_dir: Optional override for the directory containing the
                per-country JSONs. Defaults to
                ``src/database/tax_year/<tax_year>/treaties/``.
        """
        self.tax_year = tax_year
        if treaties_dir is None:
            treaties_dir = (
                Path(__file__).parent.parent
                / "database"
                / "tax_year"
                / str(tax_year)
                / "treaties"
            )
        self.treaties_dir = Path(treaties_dir)
        self.countries: Dict[str, TreatyDocument] = self._load_all_countries()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all_countries(self) -> Dict[str, TreatyDocument]:
        countries: Dict[str, TreatyDocument] = {}
        if not self.treaties_dir.is_dir():
            logger.warning(
                "Treaties directory missing: %s. No treaty benefits will apply.",
                self.treaties_dir,
            )
            return countries

        for path in sorted(self.treaties_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                doc = TreatyDocument(**raw)
                countries[doc.iso2.upper()] = doc
                if not doc.verified_against_pub901:
                    logger.debug(
                        "Treaty %s loaded but marked unverified against Pub 901.",
                        doc.iso2,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to load treaty file %s: %s", path, exc)
        return countries

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def country(self, iso2: str) -> Optional[TreatyDocument]:
        """Look up a country by ISO2 code (case-insensitive)."""
        return self.countries.get(iso2.upper())

    # ------------------------------------------------------------------
    # Article eligibility
    # ------------------------------------------------------------------

    def _article_applies(
        self,
        article: TreatyArticle,
        *,
        category: TreatyCategory,
        visa_type: str,
        is_us_source: Optional[bool],
        years_since_arrival: int,
        residency_status: str,
    ) -> bool:
        """Return True when the article covers this category/visa/source/year."""
        if article.category != category:
            return False

        if article.covered_visas and visa_type not in article.covered_visas:
            return False

        if article.source_restriction == "us_source_only" and is_us_source is False:
            return False
        if article.source_restriction == "foreign_source_only" and is_us_source is True:
            return False

        if article.max_year_cap is not None and years_since_arrival > article.max_year_cap:
            return False

        # Saving clause: when filer is a resident alien, only saving-clause-exception
        # articles still apply.
        if residency_status == "resident_alien" and not article.saving_clause_exception:
            return False

        return True

    def _compute_exempt_amount(
        self,
        article: TreatyArticle,
        gross_amount: float,
    ) -> float:
        """Cap the exempt amount by the article's annual dollar cap, if any."""
        if article.max_dollar_cap is None:
            return max(0.0, float(gross_amount))
        return max(0.0, min(float(gross_amount), float(article.max_dollar_cap)))

    def _form_8833_required(
        self,
        article: TreatyArticle,
        exempt_amount: float,
    ) -> bool:
        """Apply IRC §6114 disclosure rule with the Notice 2010-21 exception."""
        if article.notice_2010_21_exception:
            return False
        threshold = article.requires_form_8833_if_over
        if threshold is None:
            return True
        return exempt_amount > threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        country: str,
        visa_type: str,
        residency_status: str,
        years_since_arrival: int,
        gross_by_category: Dict[TreatyCategory, float],
        is_us_source_by_category: Optional[Dict[TreatyCategory, Optional[bool]]] = None,
    ) -> List[AppliedTreatyBenefit]:
        """Return every concrete treaty benefit applicable to this filer.

        Args:
            country: ISO2 code or country name; ISO2 is preferred for stability.
            visa_type: e.g. ``"F-1"``, ``"J-1"``, ``"H-1B"``.
            residency_status: ``"nonresident_alien"``, ``"resident_alien"``, or ``"dual_status"``.
            years_since_arrival: Calendar years counted from first US arrival.
            gross_by_category: Dict mapping each :data:`TreatyCategory` to the gross
                US-source (or specified-source) amount the filer is claiming an
                exemption against.
            is_us_source_by_category: Optional override for source classification
                of each category. When omitted, the evaluator assumes US-source
                for ``student_personal_services`` and ``teaching_research``,
                and treats other categories as "either" (unrestricted).

        Returns:
            A list of :class:`AppliedTreatyBenefit` — one entry per matching article.
            Returns an empty list when no treaty applies or every article is filtered out.
        """
        doc = self.country(country)
        if doc is None or not doc.treaty_in_force:
            return []

        if is_us_source_by_category is None:
            is_us_source_by_category = {}

        results: List[AppliedTreatyBenefit] = []

        for article in doc.articles:
            gross = gross_by_category.get(article.category, 0.0)
            if gross <= 0:
                continue

            is_us_source = is_us_source_by_category.get(article.category)

            if not self._article_applies(
                article,
                category=article.category,
                visa_type=visa_type,
                is_us_source=is_us_source,
                years_since_arrival=years_since_arrival,
                residency_status=residency_status,
            ):
                continue

            exempt = self._compute_exempt_amount(article, gross)
            if exempt <= 0:
                continue

            requires_8833 = self._form_8833_required(article, exempt)

            explanation = self._build_explanation(doc, article, exempt)

            results.append(
                AppliedTreatyBenefit(
                    country_iso2=doc.iso2,
                    country_name=doc.country_name,
                    article_id=article.article_id,
                    category=article.category,
                    exempt_amount=exempt,
                    rate_override=0.0 if exempt >= gross else None,
                    applies_after_saving_clause=article.saving_clause_exception
                    and residency_status == "resident_alien",
                    requires_form_8833=requires_8833,
                    explanation=explanation,
                )
            )

        return results

    def _build_explanation(
        self,
        doc: TreatyDocument,
        article: TreatyArticle,
        exempt_amount: float,
    ) -> str:
        bits = [
            f"US-{doc.country_name} treaty Article {article.article_id} "
            f"({article.category}): exempts ${exempt_amount:,.0f}",
        ]
        if article.max_dollar_cap is not None:
            bits.append(f"annual cap ${article.max_dollar_cap:,.0f}")
        if article.max_year_cap is not None:
            bits.append(f"max {article.max_year_cap}-year window")
        if article.saving_clause_exception:
            bits.append("saving-clause exception applies")
        return "; ".join(bits) + "."

    # ------------------------------------------------------------------
    # Aggregators
    # ------------------------------------------------------------------

    @staticmethod
    def aggregate_form_8833_required(benefits: List[AppliedTreatyBenefit]) -> bool:
        """Return True if any benefit individually triggers a Form 8833."""
        return any(b.requires_form_8833 for b in benefits)

    @staticmethod
    def total_exempt_by_category(
        benefits: List[AppliedTreatyBenefit],
    ) -> Dict[TreatyCategory, float]:
        """Sum exempt amounts per category (useful for state mutation)."""
        totals: Dict[TreatyCategory, float] = {}
        for b in benefits:
            totals[b.category] = totals.get(b.category, 0.0) + b.exempt_amount
        return totals
