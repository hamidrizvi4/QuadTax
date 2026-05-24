"""Intake payload schema.

Defines the full set of fields the client collects from the filer and posts
to the API. The same Pydantic model drives both:

    1. The FastAPI request body validation (and therefore the auto-generated
       OpenAPI schema the client codegens TypeScript from), and
    2. The :class:`MCQRouter` which projects the intake into the initial
       :class:`ReturnStateObject` before the L1-L9 pipeline runs.

Keeping these together kills the previous hand-rolled-interface drift between
``nra-tax-client/src/store/taxStore.ts`` and the engine.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FilingStatus = Literal["single", "mfs", "qss"]


class IntakeIdentity(BaseModel):
    """Demographic, identifier, and address fields."""

    model_config = ConfigDict(extra="forbid")

    first_name: str = ""
    middle_initial: str = ""
    last_name: str = ""
    suffix: str = ""
    date_of_birth: Optional[str] = Field(
        default=None, description="ISO date (YYYY-MM-DD)."
    )

    ssn: str = Field(default="", description="9 digits, no dashes. Empty if no SSN.")
    itin: str = Field(default="", description="9 digits, no dashes. Empty if no ITIN.")

    country_of_citizenship: str = Field(default="", description="ISO2 country code.")
    country_of_tax_residence: str = Field(default="", description="ISO2 country code.")
    passport_number: str = ""
    passport_country: str = Field(default="", description="ISO2 country code.")

    us_address_line1: str = ""
    us_address_line2: str = ""
    us_city: str = ""
    us_state: str = ""
    us_zip: str = ""

    foreign_address_line1: str = ""
    foreign_address_line2: str = ""
    foreign_city: str = ""
    foreign_state_province: str = ""
    foreign_country: str = ""
    foreign_postal_code: str = ""

    occupation: str = "Student"
    daytime_phone: str = ""
    email: str = ""

    filing_status: FilingStatus = "single"
    spouse_first_name: str = ""
    spouse_last_name: str = ""
    spouse_ssn_or_itin: str = ""


class IntakeResidency(BaseModel):
    """Residency / visa context. The OCR'd I-94 supplies the day counts."""

    model_config = ConfigDict(extra="forbid")

    tax_year: int = Field(default=2025, ge=2024)
    visa_type: str = Field(default="F-1")
    visa_subtype: Literal["student", "teacher_researcher", "trainee", "other"] = "student"
    first_us_arrival_year: int = Field(default=2024, ge=1900)
    prior_us_visa_history: List[str] = Field(
        default_factory=list,
        description=(
            "ISO date strings or 'YYYY' for each prior visa entry. Used to "
            "compute the cumulative 5-year exempt window."
        ),
    )
    prior_year_residency_status: Literal["nonresident_alien", "resident_alien", "none"] = "none"


class IntakeIncome(BaseModel):
    """Income context the LLM-OCR alone can't supply."""

    model_config = ConfigDict(extra="forbid")

    income_description: str = Field(
        default="",
        description=(
            "Free-text description of the filer's primary income source. "
            "Drives the L4 LLM treaty-category classifier."
        ),
    )
    requires_services: bool = Field(
        default=False,
        description="True if the filer's grant required services (drives Code 16 routing).",
    )
    is_qualified_expense: bool = Field(
        default=False,
        description="True if a scholarship is for tuition/fees only (§117 exclusion).",
    )
    prior_year_treaty_claim_total: float = Field(
        default=0.0,
        ge=0.0,
        description="For Schedule OI Item L — prior-year treaty exempt amount.",
    )


class IntakeNYContext(BaseModel):
    """NY-specific MCQ answers (set to None to skip the NY pipeline)."""

    model_config = ConfigDict(extra="forbid")

    days_in_ny: int = Field(default=0, ge=0, le=366)
    has_permanent_abode_in_ny: bool = False
    abode_months_in_year: int = Field(default=0, ge=0, le=12)
    is_student_dorm: bool = True
    domiciled_in_ny: bool = False
    moved_into_ny_mid_year: bool = False
    moved_out_of_ny_mid_year: bool = False
    nyc_address: bool = False
    yonkers_address: bool = False
    ny_work_days: int = Field(default=0, ge=0, le=366)
    total_work_days: int = Field(default=0, ge=0, le=366)
    employer_in_ny: bool = True
    institution_1042s_in_ny: bool = True


class IntakeFICA(BaseModel):
    """FICA-refund-claim context (Form 843 path)."""

    model_config = ConfigDict(extra="forbid")

    employer_attempted_refund: bool = Field(
        default=False,
        description="True if the employer was asked to refund FICA and refused.",
    )
    has_form_8316: bool = Field(
        default=False,
        description="True if the employer-refusal Form 8316 is in hand.",
    )
    employer_name: str = ""
    employer_ein: str = ""


class IntakeBanking(BaseModel):
    """Direct-deposit routing info for federal refunds."""

    model_config = ConfigDict(extra="forbid")

    direct_deposit: bool = False
    routing_number: str = Field(default="", description="9-digit routing number.")
    account_number: str = ""
    account_type: Literal["checking", "savings", ""] = ""


class IntakeElections(BaseModel):
    """Tax elections / disclosures the user has previously made."""

    model_config = ConfigDict(extra="forbid")

    section_6013g_election: bool = Field(
        default=False,
        description="§6013(g): NRA spouse of US person elected to be treated as resident.",
    )
    section_6013h_election: bool = False
    section_871d_election: bool = Field(
        default=False,
        description="§871(d): real-property income treated as ECI.",
    )
    large_foreign_gifts_over_100k: bool = False
    closer_connection_exception_claimed: bool = False


class IntakePayload(BaseModel):
    """Top-level intake payload — POSTed to /api/v1/upload-and-process."""

    model_config = ConfigDict(extra="forbid")

    identity: IntakeIdentity
    residency: IntakeResidency
    income: IntakeIncome
    ny: Optional[IntakeNYContext] = Field(
        default=None,
        description="Set to a populated object when the filer has any NY footprint.",
    )
    fica: IntakeFICA = Field(default_factory=IntakeFICA)
    banking: IntakeBanking = Field(default_factory=IntakeBanking)
    elections: IntakeElections = Field(default_factory=IntakeElections)
