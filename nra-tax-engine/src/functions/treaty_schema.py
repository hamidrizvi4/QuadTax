"""Pydantic schemas for tax-treaty data.

Each US income-tax-treaty partner country lives in its own JSON file under
``src/database/tax_year/<year>/treaties/<ISO2>.json``. The schema below
captures the per-article rules a NRA filer encounters: covered visa types,
dollar/year caps, source restrictions, saving-clause-exception coverage,
and Form 8833 disclosure thresholds.

Design choices:
    * One file per country — smaller diffs, easier per-country authorship.
    * ``articles`` is a list (not a dict) so the same category may appear
      twice when a country has multiple provisions touching the same income
      type (rare; included for safety).
    * Categories are an enum so the L4 treaty-mapping agent is forced to
      emit one of the known values; ``none`` short-circuits eligibility.
    * Money values stay as plain floats here for readability; the evaluator
      coerces to ``decimal.Decimal`` when applying caps.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums — closed sets the LLM and downstream code can rely on
# ---------------------------------------------------------------------------

TreatyCategory = Literal[
    "scholarship_fellowship",         # Income code 16 — fellowship/scholarship grant
    "student_personal_services",      # Wages earned by a student (US-source)
    "apprentice_trainee",             # Apprentice or business trainee (separate from "student")
    "teaching_research",              # Visiting professor / researcher (Code 19)
    "independent_personal_services",  # Code 17 — non-employee compensation
    "dependent_personal_services",    # Code 18 — employee compensation
    "pension_annuity",                # Code 15
    "social_security",                # Code 14
    "government_service",             # Code 25
    "foreign_source_remittance",      # UK/Canada/Japan-style — exempt if income source is foreign
    "none",                           # No treaty article applies to this income
]

SourceRestriction = Literal[
    "us_source_only",
    "foreign_source_only",
    "any_source",
]

YearCountingRule = Literal[
    "from_first_arrival",      # 5-year exempt window starts at first US arrival
    "from_arrival_in_status",  # Counts only years in the current treaty-relevant status
    "consecutive_only",        # Must be consecutive, breaks reset the counter
    "cumulative",              # Each calendar year touched counts
    "none",                    # No year limit
]


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------


class TreatyArticle(BaseModel):
    """One article (or sub-paragraph) of a tax treaty as it bears on an NRA filer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    article_id: str = Field(
        ...,
        description="Article identifier as published, e.g. '20(c)', '21(1)', 'XIII(1)'.",
    )
    category: TreatyCategory = Field(
        ...,
        description="Tax category this article covers; matches the L4 mapping enum.",
    )
    covered_visas: List[str] = Field(
        default_factory=list,
        description="Visa types the benefit is available to (e.g. 'F-1', 'J-1'). Empty = applies to any.",
    )
    max_dollar_cap: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Per-year dollar cap on exempt amount. None = unlimited.",
    )
    max_year_cap: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum number of years the benefit may be claimed. None = unlimited.",
    )
    year_counting_rule: YearCountingRule = Field(
        default="none",
        description="How the year window is counted.",
    )
    source_restriction: SourceRestriction = Field(
        default="any_source",
        description="Whether the income must be US-source, foreign-source, or either.",
    )
    saving_clause_exception: bool = Field(
        default=False,
        description=(
            "True if this article survives the saving clause — i.e., the benefit "
            "remains available even after the filer transitions to resident-alien "
            "status. Example: US-China Protocol para 2 preserves Art 20 benefits."
        ),
    )
    saving_clause_exception_cite: Optional[str] = Field(
        default=None,
        description="Citation for the saving-clause exception (protocol paragraph, MOU, etc.).",
    )
    requires_form_8833_if_over: Optional[float] = Field(
        default=10000.0,
        ge=0.0,
        description=(
            "Dollar threshold above which Form 8833 disclosure is required under "
            "IRC §6114 and Treas. Reg. §301.6114-1. None = always required for this article. "
            "Set to a high number (or use the Notice 2010-21 exception flag) when no "
            "disclosure is needed for routine claims."
        ),
    )
    notice_2010_21_exception: bool = Field(
        default=False,
        description=(
            "If true, Form 8833 is NOT required for this claim regardless of amount, "
            "per Rev. Proc. 2007-66 / Notice 2010-21. Applies to enumerated routine "
            "treaty positions for individuals (e.g., student-wage exemptions)."
        ),
    )
    pub901_table_ref: Optional[str] = Field(
        default=None,
        description="Pub 901 table + row reference, e.g. 'Table 2, China'. For audit traceability.",
    )
    note: Optional[str] = Field(
        default=None,
        description="Free-form note describing edge cases, IRS guidance, or implementation caveats.",
    )


class SavingClause(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    exists: bool = False
    cite: Optional[str] = None
    exception_paragraph: Optional[str] = None


class TreatyDocument(BaseModel):
    """Top-level treaty record for one US treaty partner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    country_name: str
    iso2: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2.")
    treaty_in_force: bool = True
    treaty_effective_date: Optional[str] = Field(
        default=None, description="ISO date the treaty (or last protocol) entered into force."
    )
    saving_clause: SavingClause = Field(default_factory=SavingClause)
    articles: List[TreatyArticle] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    verified_against_pub901: bool = Field(
        default=False,
        description=(
            "True once a human has cross-checked every article in this file "
            "against the current Pub 901 tables. Unverified countries still load "
            "but the evaluator logs a warning."
        ),
    )


# ---------------------------------------------------------------------------
# Applied-benefit result type (returned by TreatyEvaluator)
# ---------------------------------------------------------------------------


class AppliedTreatyBenefit(BaseModel):
    """One concrete treaty benefit applied to a filer's income."""

    model_config = ConfigDict(extra="forbid")

    country_iso2: str
    country_name: str
    article_id: str
    category: TreatyCategory
    exempt_amount: float = Field(ge=0.0)
    rate_override: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Treaty-reduced flat rate (FDAP path)."
    )
    applies_after_saving_clause: bool = False
    requires_form_8833: bool = False
    explanation: str = Field(
        default="",
        description="Human-readable explanation produced for the audit log and 8833 box 5.",
    )
