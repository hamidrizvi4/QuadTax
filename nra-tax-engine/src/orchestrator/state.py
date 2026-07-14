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


class TaxpayerIdentityState(BaseModel):
    """Demographic and identifier fields required by every IRS form.

    Populated from the intake/MCQ layer. Each field maps to one or more
    AcroForm fields across the federal forms.
    """

    first_name: str = Field(default="", description="Legal first name as on passport.")
    middle_initial: str = Field(default="", description="Middle initial, blank if none.")
    last_name: str = Field(default="", description="Legal last (family) name.")
    suffix: str = Field(default="", description="Jr/Sr/III, blank if none.")
    date_of_birth: Optional[str] = Field(
        default=None, description="ISO date (YYYY-MM-DD)."
    )

    ssn: str = Field(
        default="",
        description=(
            "Social Security Number as 9 digits without dashes. Empty if the "
            "filer has no SSN — then ``itin`` is used."
        ),
    )
    itin: str = Field(
        default="",
        description=(
            "Individual Taxpayer Identification Number, 9 digits without "
            "dashes. Used when no SSN. If both are empty, Form W-7 must be "
            "attached on the first filing."
        ),
    )
    requires_w7_application: bool = Field(
        default=False,
        description="True when neither SSN nor ITIN is present — triggers Form W-7.",
    )

    country_of_citizenship: str = Field(default="", description="ISO2 country code.")
    country_of_tax_residence: str = Field(
        default="", description="ISO2 country code for treaty purposes."
    )
    passport_number: str = Field(default="")
    passport_country: str = Field(default="", description="ISO2 country code.")

    us_address_line1: str = Field(default="")
    us_address_line2: str = Field(default="")
    us_city: str = Field(default="")
    us_state: str = Field(default="", description="2-letter US state postal code.")
    us_zip: str = Field(default="")

    foreign_address_line1: str = Field(default="")
    foreign_address_line2: str = Field(default="")
    foreign_city: str = Field(default="")
    foreign_state_province: str = Field(default="")
    foreign_country: str = Field(default="", description="ISO2 country code.")
    foreign_postal_code: str = Field(default="")

    occupation: str = Field(
        default="Student",
        description="Free-text occupation; appears on 1040-NR signature block.",
    )
    daytime_phone: str = Field(default="")
    email: str = Field(default="")

    filing_status: Literal["single", "mfs", "qss"] = Field(
        default="single",
        description="NRA-permitted filing status. MFJ and HOH are not allowed on 1040-NR.",
    )

    # Verified against every vendored TY2025 form (1040-NR, Schedule OI/A/NEC)
    # via a full-text search for "spouse": none has a spouse name/SSN field
    # to map these to — the 1040-NR's only "Spouse" label is a date-of-death
    # box, not an identification line. Kept for forward-compatibility (e.g.
    # a future MFJ-adjacent form) rather than removed; deliberately not
    # wired to any populator since no real target exists today.
    spouse_first_name: str = Field(default="")
    spouse_last_name: str = Field(default="")
    spouse_ssn_or_itin: str = Field(default="")

    @property
    def primary_tin(self) -> str:
        """Return SSN if present, else ITIN, else empty string."""
        return self.ssn or self.itin


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
            "(current × 1 + prior_1 × 1/3 + prior_2 × 1/6 ≥ 183). Do NOT use "
            "this for Form 8843 line 4a, which wants raw physical presence "
            "regardless of exempt status — use days_present_* below instead."
        ),
    )

    days_present_current_year: int = Field(
        default=0,
        ge=0,
        le=366,
        description=(
            "Raw days physically present in the US during the current tax "
            "year, BEFORE any exempt-individual exclusion — unlike "
            "spt_days_current_year, this is never zeroed out for an exempt "
            "F/J/M/Q filer. This is what Form 8843 Part I line 4a asks for."
        ),
    )
    days_present_year_minus_1: int = Field(
        default=0, ge=0, le=366,
        description="Raw days physically present in the US during tax_year - 1.",
    )
    days_present_year_minus_2: int = Field(
        default=0, ge=0, le=366,
        description="Raw days physically present in the US during tax_year - 2.",
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
    visa_subtype: Literal["student", "teacher_researcher", "trainee", "other"] = Field(
        default="student",
        description=(
            "Distinguishes a J-1 teacher/researcher (2-calendar-year exempt "
            "window) from a J-1 student (5-calendar-year window) — the two "
            "share the same visa_type='J-1' but have different SPT exemption "
            "periods under IRC §7701(b)(5). Only meaningful for J-1; F-1/M-1/Q-1 "
            "always use the 5-year student window regardless of this value."
        ),
    )
    prior_year_residency_status: Literal["nonresident_alien", "resident_alien", "none"] = Field(
        default="none",
        description=(
            "Filer-reported residency status for the immediately preceding "
            "tax year, from intake. Drives Schedule OI Item E disclosure "
            "('were you a US resident in a prior year?') AND, when set to "
            "'resident_alien', L1's prior_visa_was_resident input to "
            "departure-year dual-status detection."
        ),
    )

    # ── Dual-status detection inputs (intake-seeded) ───────────────────
    first_us_entry_date: Optional[str] = Field(
        default=None,
        description=(
            "ISO date of the filer's first-ever US entry, from intake. Only "
            "used by L1 for arrival-year dual-status detection when "
            "first_us_arrival_year == tax_year."
        ),
    )
    is_still_in_us: bool = Field(
        default=True,
        description="False if the filer left the US before the end of the tax year.",
    )
    intended_departure_date: Optional[str] = Field(
        default=None,
        description="ISO date the filer left the US, when is_still_in_us is False.",
    )

    # ── Dual-status detection outputs (L1-computed) ────────────────────
    is_dual_status: bool = Field(
        default=False,
        description="True when L1 detected an arrival-year or departure-year residency change.",
    )
    residency_start_date: Optional[str] = Field(
        default=None,
        description="Arrival-year dual status: the date NRA-to-RA residency began.",
    )
    residency_end_date: Optional[str] = Field(
        default=None,
        description="Departure-year dual status: the date RA-to-NRA residency ended.",
    )
    dual_status_reason: Optional[str] = Field(
        default=None,
        description="Plain-English citation explaining which dual-status trigger applied.",
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

    employer_name: str = Field(
        default="",
        description=(
            "Primary employer's name, from intake or W-2 OCR. Used on Form "
            "843's and Form 8316's employer-identification lines and NY "
            "IT-203-B Schedule A."
        ),
    )
    employer_ein: str = Field(
        default="",
        description="Primary employer's EIN, from intake or W-2 OCR. Used on Form 843.",
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
    prior_year_treaty_claim_total: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Filer-reported treaty-exempt amount claimed in the prior tax "
            "year, from intake — display-only, for Schedule OI Item L's "
            "'amount claimed in prior years' column. Does not affect the "
            "current year's exemption math (treaty caps are applied fresh "
            "per tax year)."
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
    employer_attempted_refund: bool = Field(
        default=False,
        description=(
            "Filer-confirmed: they asked their employer for a FICA refund. "
            "Treas. Reg. §31.3121(b)(19)-1 requires this before Form 843 is "
            "proper. Drives whether Form 843/8316's explanation text can "
            "assert employer refusal as a confirmed fact vs. an unconfirmed "
            "claim."
        ),
    )
    has_form_8316: bool = Field(
        default=False,
        description="Filer-confirmed: an employer-signed Form 8316 statement is in hand.",
    )


class NYTaxState(BaseModel):
    """L9 — New York state, NYC, and Yonkers tax results.

    NY runs its own residency test (separate from federal SPT) and does NOT
    honor federal tax treaties — federal treaty exemptions are added back to
    NY taxable income.
    """

    residency_status: Literal["resident", "part_year", "nonresident", "pending"] = Field(
        default="pending",
        description=(
            "NY residency classification under NY Tax Law §605. 'nonresident' "
            "is the default for F-1 students living in dorms (Knight case)."
        ),
    )
    residency_reason: str = Field(
        default="",
        description="Plain-English explanation of why this status was chosen.",
    )
    days_in_ny: int = Field(default=0, ge=0, le=366)
    nyc_resident: bool = Field(default=False)
    yonkers_resident: bool = Field(default=False)
    ny_work_days: int = Field(
        default=0, ge=0, le=366,
        description="Work days spent physically in NY — IT-203-B Schedule A.",
    )
    total_work_days: int = Field(
        default=0, ge=0, le=366,
        description="Total work days for the year (NY + elsewhere) — IT-203-B Schedule A.",
    )
    abode_months_in_year: int = Field(
        default=0, ge=0, le=12,
        description="Months a NY abode was maintained — IT-203-B Schedule B.",
    )

    ny_source_wages: float = Field(default=0.0, ge=0.0)
    ny_source_1042s_gross: float = Field(default=0.0, ge=0.0)
    ny_source_income: float = Field(default=0.0, ge=0.0)
    ny_income_percentage: float = Field(default=0.0, ge=0.0, le=1.0)

    ny_agi: float = Field(default=0.0, ge=0.0)
    ny_treaty_addback: float = Field(default=0.0, ge=0.0)
    ny_standard_deduction: float = Field(default=0.0, ge=0.0)
    ny_taxable_income: float = Field(default=0.0, ge=0.0)
    ny_tax_resident_basis: float = Field(default=0.0, ge=0.0)
    ny_tax_apportioned: float = Field(default=0.0, ge=0.0)
    nyc_tax: float = Field(default=0.0, ge=0.0)
    yonkers_tax: float = Field(default=0.0, ge=0.0)
    total_ny_state_local: float = Field(default=0.0, ge=0.0)

    ny_withholding: float = Field(
        default=0.0,
        ge=0.0,
        description="NY state income tax withheld (W-2 Box 17 totals).",
    )
    nyc_withholding: float = Field(
        default=0.0,
        ge=0.0,
        description="NYC / locality income tax withheld (W-2 Box 19 totals).",
    )
    ny_refund_or_owed: float = Field(
        default=0.0,
        description="Positive = filer owes NY; negative = NY refund.",
    )


class TaxCalculatedState(BaseModel):
    """L6 (part 2) — Final tax liability computation results.

    Contains the output of the deterministic tax_math module: graduated
    bracket calculations for ECI, flat-rate calculations for FDAP,
    and the final refund/balance-due determination.
    """

    agi: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Adjusted Gross Income for the 1040-NR (line 11). For NRA students "
            "this is gross wages + taxable FDAP, after treaty WAGE exemptions "
            "(e.g. China Art 20(c)) but BEFORE the deduction on line 12. Written "
            "authoritatively by L6 so form populators don't re-derive it."
        ),
    )

    deduction_amount: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Amount on 1040-NR line 12 — the larger of itemized (Schedule A) or "
            "the standard deduction. For NRAs the standard deduction is $0 unless "
            "the India treaty Article 21(2) applies ($15,000 single for TY2025)."
        ),
    )

    deduction_type: Literal["standard", "itemized", "none"] = Field(
        default="none",
        description="Which deduction was used on line 12.",
    )

    taxable_income: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "1040-NR line 15 — AGI minus the line 12 deduction (floored at 0). "
            "Written authoritatively by L6; the federal tax on line 16 is "
            "computed from this figure."
        ),
    )

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

    direct_deposit: bool = Field(
        default=False,
        description="True if the filer requested direct deposit for their federal refund.",
    )
    routing_number: str = Field(default="", description="9-digit ABA routing number.")
    account_number: str = Field(default="", description="Bank account number.")
    account_type: Literal["checking", "savings", ""] = Field(
        default="",
        description="Account type for direct deposit — Form 1040-NR line 35c.",
    )


class ElectionsState(BaseModel):
    """Tax elections / disclosures the filer has made, seeded from intake.

    None of these are supported by the deterministic NRA (§871) pipeline
    this engine implements — a §6013 election means filing as a full
    resident under §1 (worldwide income, a different tax regime entirely),
    large foreign gifts / the closer-connection exception each require a
    standalone form (3520 / 8840) this engine does not generate, and a
    §871(d) election requires computing real-property income as ECI, which
    has no supporting income category anywhere in this engine — checking
    Schedule OI's disclosure box without that underlying computation would
    be actively misleading, not just incomplete. When any of these is True,
    validate_post_l1 blocks automatic assembly rather than silently
    producing a return that omits a legally required disclosure or applies
    the wrong tax treatment.
    """

    section_6013g_election: bool = Field(
        default=False,
        description="§6013(g): NRA spouse of US person elected to be treated as resident.",
    )
    section_6013h_election: bool = Field(
        default=False,
        description="§6013(h): dual-status-year election to be treated as resident.",
    )
    section_871d_election: bool = Field(
        default=False,
        description="§871(d): real-property income treated as ECI — no supporting income category in this engine.",
    )
    large_foreign_gifts_over_100k: bool = Field(
        default=False,
        description="Received gifts/bequests over $100,000 from a foreign person or estate — triggers Form 3520.",
    )
    closer_connection_exception_claimed: bool = Field(
        default=False,
        description="Claiming the closer-connection-to-a-foreign-country exception — requires Form 8840.",
    )


class ExtrasState(BaseModel):
    """Miscellaneous intake answers seeded from the frontend's "extras" step.

    Consumer status per field, verified by a full-text search of every
    vendored TY2025 form (1040-NR, Schedule OI/A/NEC, 8843, 843) for
    "full-time"/"degree candidate"/"dependent"/"extension"/"OPT"/"CPT" —
    none of those strings appear anywhere, so several of these genuinely
    have no PDF field to map to, not just an unwired one:

    - filed_previous_federal_return -> Schedule OI Item H.
    - made_estimated_federal_payments / estimated_federal_payment_amount ->
      1040-NR line 26, via withholding_reconciler.
    - can_be_claimed_as_dependent -> gates the IRC §63(c)(5) capped
      standard deduction for India Article 21(2) filers (l6_tax_calc.py) —
      a real computational input, not just a display field. Defaults to
      False, matching prior (uncapped) behavior when unanswered, so this
      only ever makes the computed deduction smaller/more conservative
      relative to before, never larger.
    - was_married_on_last_day -> validate_post_l1 flags an inconsistency
      when set True alongside filing_status="single" (a married NRA must
      file MFS, never single) — a data-quality check, not a form field.
    - is_full_time_student, is_opt_cpt, filed_federal_extension -> no PDF
      field and no computational effect found (OPT/CPT doesn't change
      visa_type-driven exemption logic; this engine has no separate
      late-filing-penalty calculator for extensions to affect). Captured
      only.
    - is_degree_candidate -> IRC §117(a) technically requires degree-
      candidate status for the scholarship exclusion l3_income.py's
      is_qualified_expense gate already grants, which is a real latent
      gap — deliberately NOT wired to that gate here: this field's
      default (False when unanswered) would make the exclusion
      DISAPPEAR by default for the common case (most F-1/J-1 students
      genuinely are degree candidates but may not reach/answer this
      specific extras question), which is a worse, regression-risk
      direction unlike can_be_claimed_as_dependent above. Needs a
      required (non-nullable, no-default) intake question before it's
      safe to gate on.
    """

    is_full_time_student: bool = False
    is_degree_candidate: bool = False
    is_opt_cpt: bool = False
    had_digital_assets: bool = False
    can_be_claimed_as_dependent: bool = False
    was_married_on_last_day: bool = False
    made_estimated_federal_payments: bool = False
    estimated_federal_payment_amount: float = Field(default=0.0, ge=0.0)
    made_estimated_state_payments: bool = False
    filed_federal_extension: bool = False
    filed_previous_federal_return: bool = Field(
        default=False,
        description="Schedule OI Item H — filed a 1040 in the prior tax year.",
    )
    previous_return_year: Optional[int] = None
    previous_return_type: str = ""


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
    identity: TaxpayerIdentityState = Field(
        default_factory=TaxpayerIdentityState,
        description="Demographic and identifier fields (intake-populated).",
    )
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
    ny: NYTaxState = Field(
        default_factory=NYTaxState,
        description="L9 output: NY state, NYC, and Yonkers tax results.",
    )
    elections: ElectionsState = Field(
        default_factory=ElectionsState,
        description="Intake-populated tax elections/disclosures out of scope for this engine.",
    )
    extras: ExtrasState = Field(
        default_factory=ExtrasState,
        description="Miscellaneous intake answers from the frontend's extras step.",
    )

    # ── Pipeline-level constants ──────────────────────────────────────
    tax_year: int = Field(
        default=2025,
        ge=2024,
        description="Calendar year the return is for (e.g., 2025 for returns filed in 2026).",
    )
    filing_id: Optional[str] = Field(
        default=None,
        description=(
            "Opaque identifier for this filing — used to name audit log files "
            "and resume in-progress returns. Set by the orchestrator or API."
        ),
    )

    # ── Phase-7 reliability surface ───────────────────────────────────
    audit_trail: List[dict] = Field(
        default_factory=list,
        description=(
            "Chronological list of AuditEntry dicts (layer, function, "
            "timestamp, inputs/outputs hashes, rationale). Mutated by "
            ":func:`src.orchestrator.audit.record`. Drives the 'Why this "
            "number?' UI and IRS-notice response workflow."
        ),
    )
    requires_human_review: List[str] = Field(
        default_factory=list,
        description=(
            "Human-readable reasons why a CPA must review the return before "
            "filing. Populated by post-layer validators in "
            ":mod:`src.orchestrator.validators` and by the LLM safety wrapper. "
            "The engine refuses to set ``ready_for_assembly=True`` while "
            "this list is non-empty unless the API caller explicitly "
            "acknowledges each item."
        ),
    )

    # ── Withholding reconciliation report (Phase 2) ───────────────────
    withholding_report: dict = Field(
        default_factory=dict,
        description=(
            "Aggregated withholding totals across all sources (W-2 box 2, "
            "1042-S box 7a Ch 3/4, 1099-* box 4, estimated payments). "
            "Produced by :func:`src.functions.withholding_reconciler.reconcile`. "
            "Keys: federal_w2, federal_1042s_ch3, federal_1042s_ch4, federal_1099, "
            "federal_estimated_payments, federal_total, ss_withheld_w2, "
            "medicare_withheld_w2, state_income_tax_w2, local_income_tax_w2, "
            "sources_seen."
        ),
    )

    # ── Schedule A (NRA) itemized deductions (Phase 2) ────────────────
    sch_a: dict = Field(
        default_factory=dict,
        description=(
            "NRA Schedule A result: state_local_income_tax (capped at $10k), "
            "charitable_cash, charitable_noncash, casualty_disaster_loss, "
            "other_itemized, total, disallowed_items[]. Populated by "
            ":func:`src.functions.sch_a_nra.compute_sch_a_nra`."
        ),
    )

    # ── AMT / Form 6251 (Phase 3) ──────────────────────────────────────
    amt: dict = Field(
        default_factory=dict,
        description=(
            "Alternative Minimum Tax result: amti, exemption, "
            "tentative_minimum_tax, regular_tax_for_amt, amt_owed, binds. "
            "Populated by :class:`AMTCalculator`."
        ),
    )

    # ── ITIN / Form W-7 eligibility (Phase 3) ──────────────────────────
    itin_eligibility: dict = Field(
        default_factory=dict,
        description=(
            "ITIN application/renewal result: needs_w7, reason_code, "
            "is_renewal, explanation. Drives Form W-7 attachment."
        ),
    )

    # ── Estimated tax penalty / Form 2210 (Phase 3) ────────────────────
    estimated_tax_penalty: dict = Field(
        default_factory=dict,
        description=(
            "Form 2210 result: safe_harbor_met, safe_harbor_reason, "
            "penalty_amount, must_attach_form_2210. Worst-case estimate "
            "produced by :func:`estimated_tax_penalty.evaluate`."
        ),
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
