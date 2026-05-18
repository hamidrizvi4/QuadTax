"""
ReturnStateObject — The single mutable state object for the entire tax return.

This is the central Pydantic model that flows through the orchestrator.
Every agent and function reads from and writes to this object. It enforces
strict typing via Pydantic and ``Literal`` constraints so that no agent
hallucination or garbage data can propagate between layers.

Design:
    - Each processing layer has its own sub-model (ResidencyState, IncomeState,
      TreatyState, FicaState, TaxCalculatedState).
    - Fields start at deterministic defaults (0, False, "pending") so the
      object is always in a valid state.
    - The orchestrator uses ``completed_layers`` to enforce dependency ordering.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-Models — one per processing layer
# ---------------------------------------------------------------------------


class ResidencyState(BaseModel):
    """L1 — Tax residency determination results.

    Captures the output of the Substantial Presence Test (SPT) and
    the reasoning agent's final residency classification.
    """

    status: Literal["nonresident_alien", "resident_alien", "dual_status", "pending"] = Field(
        default="pending",
        description=(
            "Final residency classification under IRC §7701(b). "
            "'nonresident_alien' means the individual is taxed only on US-source "
            "income under IRC §871. 'resident_alien' means worldwide income is "
            "taxable under §1. 'dual_status' applies when residency changed "
            "mid-year. 'pending' means L1 has not yet completed."
        ),
    )

    spt_days_current_year: int = Field(
        default=0,
        ge=0,
        le=366,
        description=(
            "Number of days physically present in the US during the current tax "
            "year, as counted by the deterministic SPT calculator. Does NOT "
            "include exempt days for F/J/Q visa holders (those are subtracted "
            "before this value is set). Used as input to the SPT formula "
            "(current × 1 + prior_1 × 1/3 + prior_2 × 1/6 ≥ 183)."
        ),
    )

    exempt_visa_type: Optional[str] = Field(
        default=None,
        description=(
            "The visa category that qualifies the individual as an 'exempt "
            "individual' under IRC §7701(b)(5). Common values: 'F-1', 'J-1', "
            "'M-1', 'Q-1'. When set, the SPT calculator excludes the "
            "individual's days of presence for the applicable exempt period "
            "(5 calendar years for F-1; 2 for J-1 researchers). None means "
            "no exempt visa applies."
        ),
    )

    years_in_exempt_status: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of calendar years the individual has already spent in "
            "exempt status. F-1 students are exempt for up to 5 calendar years; "
            "J-1 teachers/researchers for 2. Once this exceeds the visa-type "
            "limit, days begin counting toward the SPT."
        ),
    )

    is_exempt_individual: bool = Field(
        default=False,
        description=(
            "True if the individual currently qualifies as an 'exempt individual' "
            "under IRC §7701(b)(5)(A)–(D). When True, the individual's days of "
            "presence do NOT count toward the Substantial Presence Test, and "
            "they are classified as a nonresident alien regardless of the "
            "day-count arithmetic."
        ),
    )


class IncomeState(BaseModel):
    """L3 — Income classification results.

    Captures all US-source income broken down by tax treatment category.
    The distinction between ECI and FDAP is critical because they are
    taxed under completely different regimes for NRAs.
    """

    total_w2_wages: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Aggregate gross wages from all W-2 forms (Box 1). This is the "
            "primary source of Effectively Connected Income (ECI) for most "
            "F-1/J-1 students employed on-campus or via CPT/OPT. Reported on "
            "Form 1040-NR, Line 1a."
        ),
    )

    total_1042s_gross: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Aggregate gross income from all 1042-S forms (Box 2). Includes "
            "scholarships, fellowships, royalties, and other income types "
            "subject to withholding under Chapter 3 or 4 of the IRC. Each "
            "1042-S entry is routed by income code via the deterministic "
            "code mapper to its appropriate 1040-NR line."
        ),
    )

    eci_taxable_total: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Total Effectively Connected Income (ECI) — income connected to "
            "a US trade or business under IRC §871(b). ECI is taxed at "
            "graduated rates (the same brackets as US citizens), allowing "
            "deductions. Primarily wages, self-employment income, and certain "
            "scholarship income used for non-qualified expenses."
        ),
    )

    fdap_taxable_total: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Total Fixed, Determinable, Annual, Periodical (FDAP) income "
            "under IRC §871(a). FDAP is taxed at a flat 30% (or reduced "
            "treaty rate) with NO deductions allowed. Common FDAP items: "
            "interest, dividends, royalties, non-qualified scholarship income "
            "not connected to a US trade or business."
        ),
    )

    exempt_scholarship_total: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Total scholarship/fellowship income that qualifies for exclusion "
            "under IRC §117 (used for tuition and required fees at a qualified "
            "educational institution). This amount is NOT included in taxable "
            "income. It must be subtracted from gross 1042-S scholarship "
            "amounts before computing ECI or FDAP totals."
        ),
    )

    total_w2_withholding: float = Field(
        default=0.0,
        ge=0.0,
        description="Aggregate federal income tax withheld from all W-2s (Box 2)."
    )

    total_1042s_withholding: float = Field(
        default=0.0,
        ge=0.0,
        description="Aggregate federal tax withheld from all 1042-S forms (Box 7a)."
    )

    raw_ss_withheld: float = Field(
        default=0.0,
        ge=0.0,
        description="Aggregate Social Security tax erroneously withheld from W-2s (Box 4)."
    )

    raw_medicare_withheld: float = Field(
        default=0.0,
        ge=0.0,
        description="Aggregate Medicare tax erroneously withheld from W-2s (Box 6)."
    )

class TreatyState(BaseModel):
    """L6 (part 1) — Tax treaty application results.

    Captures whether the individual's country of tax residence has an
    income tax treaty with the US and, if so, which article(s) exempt
    a portion of their income. Multi-article countries (China, India, Korea,
    etc.) populate ``applied_benefits`` with one entry per matching article;
    the scalar fields below remain for backward compatibility and reflect
    the *primary* (largest-exemption) benefit.
    """

    is_eligible: bool = Field(
        default=False,
        description=(
            "True if the individual qualifies for benefits under an income "
            "tax treaty between their country of residence and the US. "
            "Eligibility requires: (a) the country has a treaty in force, "
            "(b) the individual is a resident of that country for treaty "
            "purposes, and (c) the individual satisfies the Limitation on "
            "Benefits (LOB) article, if any."
        ),
    )

    country: Optional[str] = Field(
        default=None,
        description=(
            "ISO 3166-1 alpha-2 country code of the treaty partner country "
            "(e.g. 'IN' for India, 'CN' for China, 'KR' for South Korea). "
            "Looked up in database/tax_year/<year>/treaties/. None if no treaty applies."
        ),
    )

    article_number: Optional[str] = Field(
        default=None,
        description=(
            "The specific treaty article that grants the primary exemption, "
            "e.g. '21(2)' for India's standard-deduction equivalent or '20(b)' "
            "for China's scholarship exemption. Reflects the article tied to "
            "the largest applied exempt amount."
        ),
    )

    exempt_amount_applied: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Total dollar amount of income exempted under treaty article(s) "
            "for this tax year, summed across all matching articles. "
            "Subtracted from gross income before applying graduated tax brackets."
        ),
    )

    applied_to_category: Optional[str] = Field(
        default=None,
        description=(
            "Primary treaty category, e.g. 'scholarship_fellowship', "
            "'student_personal_services', 'teaching_research'."
        ),
    )

    applied_benefits: List[dict] = Field(
        default_factory=list,
        description=(
            "Per-article list of applied benefits. Each entry has keys: "
            "country_iso2, country_name, article_id, category, exempt_amount, "
            "rate_override, applies_after_saving_clause, requires_form_8833, explanation. "
            "Multi-article countries (China, India) will have multiple entries."
        ),
    )

    requires_form_8833: bool = Field(
        default=False,
        description=(
            "True if any applied benefit triggers a Form 8833 disclosure "
            "under IRC §6114, considering per-article thresholds and the "
            "Notice 2010-21 exception. Drives forms_required population."
        ),
    )


class FicaState(BaseModel):
    """L8 — FICA (Social Security + Medicare) refund claim results.

    Captures whether the individual was incorrectly withheld FICA taxes
    and, if so, the amounts eligible for refund via Form 843.
    """

    is_exempt: bool = Field(
        default=False,
        description=(
            "True if the individual qualifies for the FICA exemption under "
            "IRC §3121(b)(19). Nonresident aliens on F-1, J-1, M-1, or Q-1 "
            "visas performing services to carry out the purpose for which "
            "they were admitted are exempt from Social Security and Medicare "
            "taxes. Once the individual becomes a resident alien (e.g., after "
            "5 years on F-1), the exemption no longer applies."
        ),
    )

    incorrect_ss_withheld: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Dollar amount of Social Security (OASDI) tax that was "
            "erroneously withheld by the employer. Sourced from W-2 Box 4. "
            "If the individual is FICA-exempt, this entire amount is "
            "refundable via Form 843."
        ),
    )

    incorrect_medicare_withheld: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Dollar amount of Medicare (HI) tax that was erroneously "
            "withheld by the employer. Sourced from W-2 Box 6. "
            "If the individual is FICA-exempt, this entire amount is "
            "refundable via Form 843."
        ),
    )

    requires_form_843: bool = Field(
        default=False,
        description=(
            "True if the individual must file IRS Form 843 (Claim for "
            "Refund and Request for Abatement) to recover the incorrectly "
            "withheld FICA taxes. Set to True when is_exempt is True AND "
            "(incorrect_ss_withheld > 0 OR incorrect_medicare_withheld > 0). "
            "The employer must first refuse to issue the refund directly."
        ),
    )


class TaxCalculatedState(BaseModel):
    """L6 (part 2) — Final tax liability computation results.

    Contains the output of the deterministic tax_math module: graduated
    bracket calculations for ECI, flat-rate calculations for FDAP,
    and the final refund/balance-due determination.
    """

    eci_tax_liability: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Tax on Effectively Connected Income computed using the "
            "graduated IRS tax brackets (10% → 37% for 2024). This is "
            "calculated by the deterministic tax_math.apply_tax_brackets() "
            "function after subtracting allowable deductions and treaty "
            "exemptions from gross ECI."
        ),
    )

    fdap_tax_liability: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Tax on Fixed, Determinable, Annual, Periodical income at the "
            "flat 30% rate (or reduced treaty rate). FDAP is taxed on the "
            "gross amount with NO deductions allowed. Reported on "
            "Form 1040-NR, Schedule NEC."
        ),
    )

    total_tax_liability: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Sum of eci_tax_liability + fdap_tax_liability + any additional "
            "taxes (self-employment, AMT, etc.) minus applicable credits. "
            "This is the final 'total tax' line on Form 1040-NR."
        ),
    )

    total_withholding_credits: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Sum of all federal tax already withheld and/or credited: "
            "W-2 Box 2 (federal income tax withheld), 1042-S Box 7 "
            "(federal tax withheld), and any estimated tax payments "
            "(Form 1040-ES (NR)). Subtracted from total_tax_liability "
            "to determine refund or amount owed."
        ),
    )

    refund_or_owed: float = Field(
        default=0.0,
        description=(
            "Final balance: total_withholding_credits - total_tax_liability. "
            "Positive = refund due to the taxpayer. "
            "Negative = additional tax owed. "
            "Zero = no payment / no refund."
        ),
    )


# ---------------------------------------------------------------------------
# Master State Object
# ---------------------------------------------------------------------------


class ReturnStateObject(BaseModel):
    """The single mutable state object for the entire NRA tax return.

    This object is created at the start of processing and flows through
    every layer of the orchestrator. Each agent and deterministic function
    reads from and writes to the relevant sub-model.

    Layer dependency order:
        L1 (Residency) → L3 (Income) → L6 (Tax Calc) → L8 (FICA) → Assembly

    The ``completed_layers`` list tracks which layers have finished so the
    engine can enforce prerequisites before executing the next layer.
    """

    # ── Processing layer sub-models ────────────────────────────────────
    residency: ResidencyState = Field(
        default_factory=ResidencyState,
        description="L1 output: tax residency determination.",
    )
    income: IncomeState = Field(
        default_factory=IncomeState,
        description="L3 output: classified and categorized income.",
    )
    treaty: TreatyState = Field(
        default_factory=TreatyState,
        description="L6 output (part 1): treaty eligibility and exemptions.",
    )
    fica: FicaState = Field(
        default_factory=FicaState,
        description="L8 output: FICA exemption and refund amounts.",
    )
    tax: TaxCalculatedState = Field(
        default_factory=TaxCalculatedState,
        description="L6 output (part 2): computed tax liability and refund.",
    )

    # ── Assembly metadata ──────────────────────────────────────────────
    forms_required: List[str] = Field(
        default_factory=list,
        description=(
            "List of IRS / state form identifiers that must be generated "
            "for this return. Populated by the orchestrator as layers "
            "complete. Common values: '1040-NR', '8843', '843', 'IT-203'. "
            "Form 8843 is required for ALL NRAs; 1040-NR is required if "
            "the individual has US-source income; 843 is required only if "
            "a FICA refund claim is filed."
        ),
    )

    ready_for_assembly: bool = Field(
        default=False,
        description=(
            "Gate flag set to True by the orchestrator only after all "
            "prerequisite layers (L1, L3, L6, L8) have completed "
            "successfully and the state has passed final validation. "
            "The assembly module will refuse to populate forms unless "
            "this flag is True."
        ),
    )

    # ── Orchestrator bookkeeping ───────────────────────────────────────
    completed_layers: List[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of layer identifiers that have completed "
            "processing (e.g. ['L1', 'L3', 'L6', 'L8']). Used by the "
            "engine to enforce dependency ordering."
        ),
    )

    # ── Convenience methods ────────────────────────────────────────────

    def is_layer_complete(self, layer: str) -> bool:
        """Check if a specific processing layer has been completed.

        Args:
            layer: Layer identifier (e.g. 'L1', 'L3', 'L6', 'L8').

        Returns:
            True if the layer has been marked as complete.
        """
        return layer in self.completed_layers

    def mark_layer_complete(self, layer: str) -> None:
        """Mark a processing layer as complete.

        Idempotent — will not add duplicates.

        Args:
            layer: Layer identifier to mark as complete.
        """
        if layer not in self.completed_layers:
            self.completed_layers.append(layer)
