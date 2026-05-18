"""MCQ router — projects :class:`IntakePayload` into the engine's state.

Phase 6 replaces the previous NotImplementedError stubs with a deterministic
projection from the rich intake payload to (a) a pre-populated
:class:`ReturnStateObject` ready for the L1-L9 pipeline, and (b) the
legacy ``mcq_answers`` dict the orchestrator's older API consumed.

There is no LLM call in this module — every mapping is a direct copy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from src.intake.intake_schema import IntakePayload

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class MCQRouter:
    """Deterministic projector from :class:`IntakePayload` to engine inputs."""

    def populate_state(self, payload: IntakePayload) -> "ReturnStateObject":
        """Return a fresh :class:`ReturnStateObject` seeded from ``payload``."""
        from src.orchestrator.state import ReturnStateObject

        state = ReturnStateObject(tax_year=payload.residency.tax_year)

        ident = state.identity
        p = payload.identity
        ident.first_name = p.first_name
        ident.middle_initial = p.middle_initial
        ident.last_name = p.last_name
        ident.suffix = p.suffix
        ident.date_of_birth = p.date_of_birth
        ident.ssn = p.ssn
        ident.itin = p.itin
        ident.country_of_citizenship = p.country_of_citizenship
        ident.country_of_tax_residence = p.country_of_tax_residence
        ident.passport_number = p.passport_number
        ident.passport_country = p.passport_country
        ident.us_address_line1 = p.us_address_line1
        ident.us_address_line2 = p.us_address_line2
        ident.us_city = p.us_city
        ident.us_state = p.us_state
        ident.us_zip = p.us_zip
        ident.foreign_address_line1 = p.foreign_address_line1
        ident.foreign_address_line2 = p.foreign_address_line2
        ident.foreign_city = p.foreign_city
        ident.foreign_state_province = p.foreign_state_province
        ident.foreign_country = p.foreign_country
        ident.foreign_postal_code = p.foreign_postal_code
        ident.occupation = p.occupation
        ident.daytime_phone = p.daytime_phone
        ident.email = p.email
        ident.filing_status = p.filing_status
        ident.spouse_first_name = p.spouse_first_name
        ident.spouse_last_name = p.spouse_last_name
        ident.spouse_ssn_or_itin = p.spouse_ssn_or_itin

        # Residency seed — the L1 agent will overwrite status / day counts
        # but the visa_type and arrival year come from intake.
        state.residency.exempt_visa_type = payload.residency.visa_type

        return state

    def to_mcq_answers(self, payload: IntakePayload) -> Dict[str, Any]:
        """Project ``payload`` into the legacy mcq_answers dict the engine consumes.

        Maintains backward compatibility with
        :meth:`TaxEngine.run_full_pipeline` whose existing signature takes a
        flat dict for the orchestrator's per-layer calls.
        """
        d: Dict[str, Any] = {
            "tax_year": payload.residency.tax_year,
            "visa_type": payload.residency.visa_type,
            "first_us_arrival_year": payload.residency.first_us_arrival_year,
            "tax_residence_country": payload.identity.country_of_tax_residence,
            "income_description": payload.income.income_description,
            "requires_services": payload.income.requires_services,
            "is_qualified_expense": payload.income.is_qualified_expense,
        }
        if payload.ny is not None:
            d["ny_intake"] = payload.ny.model_dump()
        return d
